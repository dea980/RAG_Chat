from django.conf import settings
from typing import Dict, Any, List, Optional, Union
from langchain.schema import Document
import logging
import os
import json
from django.utils.timezone import now

from .providers import provider_manager

logger = logging.getLogger(__name__)

class MetaDataManager:
    """Utility class for managing system metadata"""
    
    @staticmethod
    def get(key: str, default=None) -> Any:
        """
        Get metadata value by key, with optional default value
        
        Args:
            key (str): The metadata key to retrieve
            default: Default value to return if key doesn't exist
            
        Returns:
            The metadata value or default if not found
        """
        from .models import MetaData
        try:
            metadata = MetaData.objects.get(key=key)
            return metadata.get_value()
        except MetaData.DoesNotExist:
            return default
        except Exception as e:
            logger.error(f"Error retrieving metadata for key '{key}': {str(e)}")
            return default
    
    @staticmethod
    def set(key: str, value: Any, description: Optional[str] = None) -> bool:
        """
        Set metadata value
        
        Args:
            key (str): The metadata key to set
            value (Any): The value to store
            description (str, optional): Description for this metadata entry
            
        Returns:
            bool: True if successful, False otherwise
        """
        from .models import MetaData
        try:
            metadata, created = MetaData.objects.get_or_create(key=key)
            
            # Reset all value fields
            metadata.string_value = None
            metadata.integer_value = None
            metadata.float_value = None
            metadata.boolean_value = None
            metadata.json_value = None
            
            # Set appropriate field based on value type
            if isinstance(value, str):
                metadata.string_value = value
            elif isinstance(value, int):
                metadata.integer_value = value
            elif isinstance(value, float):
                metadata.float_value = value
            elif isinstance(value, bool):
                metadata.boolean_value = value
            elif value is None:
                pass  # All fields are already None
            else:
                # Store as JSON for complex types
                metadata.set_json(value)
            
            # Update description if provided
            if description is not None:
                metadata.description = description
                
            metadata.save()
            return True
        except Exception as e:
            logger.error(f"Error setting metadata for key '{key}': {str(e)}")
            return False
    
    @staticmethod
    def delete(key: str) -> bool:
        """Delete metadata entry by key"""
        from .models import MetaData
        try:
            MetaData.objects.filter(key=key).delete()
            return True
        except Exception as e:
            logger.error(f"Error deleting metadata for key '{key}': {str(e)}")
            return False
    
    @staticmethod
    def initialize_system_metadata():
        """Initialize default system metadata if not already set"""
        from .models import MetaData
        
        # System version
        if not MetaData.objects.filter(key="system_version").exists():
            MetaDataManager.set(
                "system_version",
                "1.0.0",
                "Triple Chat system version"
            )
        
        # Vector store info
        if not MetaData.objects.filter(key="vector_store_path").exists():
            MetaDataManager.set(
                "vector_store_path",
                settings.VECTOR_STORE_PATH,
                "Path to the vector store directory"
            )
        
        # LLM model info
        if not MetaData.objects.filter(key="llm_model").exists():
            MetaDataManager.set(
                "llm_model",
                provider_manager.generation_provider_name,
                "Current LLM model in use"
            )
        
        # Embedding model info
        if not MetaData.objects.filter(key="embedding_model").exists():
            MetaDataManager.set(
                "embedding_model",
                os.getenv("GOOGLE_EMBEDDING_MODEL", "models/text-embedding-004"),
                "Current embedding model in use"
            )
        
        # Last data update timestamp
        if not MetaData.objects.filter(key="last_data_update").exists():
            MetaDataManager.set(
                "last_data_update",
                now().isoformat(),
                "Timestamp of last data update"
            )

class RAGUtils:
    """Utility class for RAG operations to reduce code duplication"""
    
    @staticmethod
    def get_vector_store():
        """Get vector store from the configured provider"""
        try:
            return provider_manager.get_vector_store()
        except Exception as e:
            logger.error(f"Error creating vector store: {str(e)}")
            raise
    
    @staticmethod
    def process_search_results(search_results, user_access_level: str = "internal"):
        """Process search results into legacy fields plus raw docs.

        Layer 2 ACL — chunks whose `metadata["sensitivity"]` exceeds the
        caller's `user_access_level` are filtered out and counted into
        `redacted_count`. Frontend uses that count to render the
        `[수정됨·N건]` ribbon (CLAUDE.md — no silent drop).
        """
        from moderation.levels import apply_acl_filter
        from moderation.filter import (
            apply as moderate_text,
            BlockedByModerationError,
        )
        from moderation.models import ModerationLog

        kept_acl, redacted_count = apply_acl_filter(search_results, user_access_level)
        # Layer 3 — keyword scan on each retained chunk (CLAUDE.md 4경계).
        kept: List = []
        for doc in kept_acl:
            try:
                mod = moderate_text(
                    doc.page_content,
                    source=ModerationLog.Source.RETRIEVAL,
                )
            except BlockedByModerationError:
                redacted_count += 1
                continue
            if mod.sanitized != doc.page_content:
                doc.page_content = mod.sanitized
            kept.append(doc)
        context = "\n".join([doc.page_content for doc in kept])
        image_paths = [
            doc.metadata["image_path"]
            for doc in kept
            if "image_path" in doc.metadata
        ]
        return {
            "context": context,
            "image_paths": image_paths,
            "docs": list(kept),
            "redacted_count": redacted_count,
        }

    @staticmethod
    def _pgvector_search(
        question: str,
        k: int,
        user_access_level: str,
        persona: str | None = None,
    ) -> tuple[list, int]:
        """pgvector similarity search with SQL-level ACL filtering.

        Returns (list[Document], redacted_count).
        ACL is enforced in the WHERE clause — no Python post-filter needed.
        - `sensitivity` = Phase A SensitivityLabel
        - `extra_metadata->audience_tier` = persona ACL (P1~P4 → tiers)
        """
        from moderation.levels import SENSITIVITY_LEVEL
        from knowledge.models import VectorChunk
        from pgvector.django import CosineDistance
        from .persona import tiers_for_persona

        query_embedding = provider_manager.get_embedding_model().embed_query(question)
        user_level_int = SENSITIVITY_LEVEL.get(user_access_level, 1)

        # Allowed sensitivities: those with level <= user's level
        allowed = [s for s, v in SENSITIVITY_LEVEL.items() if v <= user_level_int]

        # Persona × audience_tier ACL — JSONField path. internal_only 는
        # 어떤 persona 에게도 반환되지 않는다 (corpus 에서 차단됨).
        allowed_tiers = list(tiers_for_persona(persona))

        # Count redacted (would have matched but ACL blocked)
        all_results = VectorChunk.objects.order_by(
            CosineDistance("embedding", query_embedding)
        )[:k]
        total_count = all_results.count()

        results = (
            VectorChunk.objects
            .filter(sensitivity__in=allowed)
            .filter(extra_metadata__audience_tier__in=allowed_tiers)
            .order_by(CosineDistance("embedding", query_embedding))
            [:k]
        )

        docs = []
        for vc in results:
            meta = {
                "source_file": vc.source_file,
                "source_type": vc.source_type,
                "sensitivity": vc.sensitivity,
                "doc_sha256": vc.doc_sha256,
                **vc.extra_metadata,
            }
            if vc.page is not None:
                meta["page"] = vc.page
            if vc.section:
                meta["section"] = vc.section
            docs.append(Document(page_content=vc.content, metadata=meta))

        redacted_count = total_count - len(docs)
        return docs, max(redacted_count, 0)

    @staticmethod
    def get_rag_context(
        question: str,
        k: int | None = None,
        user_access_level: str = "internal",
        persona: str | None = None,
    ) -> Dict[str, Any]:
        """Retrieve RAG context (top-k raw docs + merged text) with ACL filter.

        - `user_access_level` = Phase A SensitivityLabel (대외비/internal/public)
        - `persona` = audience_tier ACL (P1/P2/P3/P4 → tiers 매핑).
          미지정 시 가장 보수적 fallback (public + retail).

        Uses pgvector when VectorChunk has data, falls back to Chroma.
        """
        if k is None:
            k = int(os.getenv("RERANKER_TOP_N", "20"))
        try:
            # Prefer pgvector if chunks exist
            from knowledge.models import VectorChunk
            if VectorChunk.objects.exists():
                docs, redacted_count = RAGUtils._pgvector_search(
                    question, k, user_access_level, persona=persona,
                )
                # Layer 3 — keyword moderation on retained chunks
                from moderation.filter import (
                    apply as moderate_text,
                    BlockedByModerationError,
                )
                from moderation.models import ModerationLog

                kept: List = []
                for doc in docs:
                    try:
                        mod = moderate_text(
                            doc.page_content,
                            source=ModerationLog.Source.RETRIEVAL,
                        )
                    except BlockedByModerationError:
                        redacted_count += 1
                        continue
                    if mod.sanitized != doc.page_content:
                        doc.page_content = mod.sanitized
                    kept.append(doc)

                context = "\n".join([d.page_content for d in kept])
                image_paths = [
                    d.metadata["image_path"]
                    for d in kept
                    if "image_path" in d.metadata
                ]
                return {
                    "context": context,
                    "image_paths": image_paths,
                    "docs": kept,
                    "redacted_count": redacted_count,
                }

            # Fallback to Chroma
            vector_store = RAGUtils.get_vector_store()
            from .persona import chroma_filter_for_persona
            persona_filter = chroma_filter_for_persona(persona)
            search_results = vector_store.similarity_search(
                question, k=k, filter=persona_filter
            )
            logger.debug(
                f"chroma search: persona={persona} filter={persona_filter} "
                f"k={k} hits={len(search_results)}"
            )
            return RAGUtils.process_search_results(
                search_results, user_access_level=user_access_level
            )
        except Exception as e:
            logger.error(f"Error in get_rag_context: {str(e)}")
            return {"context": "", "image_paths": [], "docs": [], "redacted_count": 0}
    
    @staticmethod
    def create_vector_store_from_documents(documents: List[Document]):
        """Create and persist a vector store from documents"""
        try:
            vector_store = provider_manager.create_vector_store_from_documents(documents)
            logger.info(f"Vector store created with {vector_store._collection.count()} documents")
            return vector_store
        except Exception as e:
            logger.error(f"Error creating vector store: {str(e)}")
            raise
