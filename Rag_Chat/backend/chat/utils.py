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
    def get_rag_context(
        question: str,
        k: int | None = None,
        user_access_level: str = "internal",
    ) -> Dict[str, Any]:
        """Retrieve RAG context (top-k raw docs + merged text) with ACL filter."""
        if k is None:
            k = int(os.getenv("RERANKER_TOP_N", "20"))
        try:
            vector_store = RAGUtils.get_vector_store()
            search_results = vector_store.similarity_search(question, k=k)
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
