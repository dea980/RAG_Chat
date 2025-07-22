from typing import Dict, Any, List, Optional, Union
import logging
from django.db import transaction
from .models import MetaData, RagData
from .utils import MetaDataManager, RAGUtils
import json
from langchain.schema import Document

logger = logging.getLogger(__name__)

class VectorMetadataManager:
    """
    Specialized utility class for managing vector search metadata.
    This helps optimize search performance by storing metadata separately.
    """
    
    # Constants for metadata key prefixes
    DOC_PREFIX = "vector_doc_"
    INDEX_PREFIX = "vector_index_"
    STATS_PREFIX = "vector_stats_"
    
    @staticmethod
    def store_document_metadata(
        doc_id: Union[str, int],
        metadata: Dict[str, Any],
        description: Optional[str] = None
    ) -> bool:
        """
        Store metadata for a vector document.
        
        Args:
            doc_id: Document ID
            metadata: Dictionary of metadata to store
            description: Optional description
            
        Returns:
            bool: Success status
        """
        key = f"{VectorMetadataManager.DOC_PREFIX}{doc_id}"
        return MetaDataManager.set(
            key=key,
            value=metadata,
            description=description or f"Vector document metadata for {doc_id}"
        )
    
    @staticmethod
    def get_document_metadata(doc_id: Union[str, int]) -> Dict[str, Any]:
        """
        Retrieve metadata for a vector document.
        
        Args:
            doc_id: Document ID
            
        Returns:
            Dict containing document metadata or empty dict if not found
        """
        key = f"{VectorMetadataManager.DOC_PREFIX}{doc_id}"
        result = MetaDataManager.get(key, {})
        return result if result is not None else {}
    
    @staticmethod
    def update_document_metadata(
        doc_id: Union[str, int],
        metadata_updates: Dict[str, Any]
    ) -> bool:
        """
        Update specific fields in document metadata.
        
        Args:
            doc_id: Document ID
            metadata_updates: Dictionary of metadata fields to update
            
        Returns:
            bool: Success status
        """
        key = f"{VectorMetadataManager.DOC_PREFIX}{doc_id}"
        current_metadata = MetaDataManager.get(key, {})
        
        if current_metadata is None:
            current_metadata = {}
            
        # Update metadata with new values
        current_metadata.update(metadata_updates)
        
        return MetaDataManager.set(
            key=key,
            value=current_metadata,
            description=f"Vector document metadata for {doc_id}"
        )
    
    @staticmethod
    def delete_document_metadata(doc_id: Union[str, int]) -> bool:
        """
        Delete metadata for a vector document.
        
        Args:
            doc_id: Document ID
            
        Returns:
            bool: Success status
        """
        key = f"{VectorMetadataManager.DOC_PREFIX}{doc_id}"
        return MetaDataManager.delete(key)
    
    @staticmethod
    def create_search_index(index_name: str, index_data: Dict[str, Any]) -> bool:
        """
        Create a search index metadata.
        
        Args:
            index_name: Name of the index
            index_data: Dictionary containing index data
            
        Returns:
            bool: Success status
        """
        key = f"{VectorMetadataManager.INDEX_PREFIX}{index_name}"
        return MetaDataManager.set(
            key=key,
            value=index_data,
            description=f"Vector search index {index_name}"
        )
    
    @staticmethod
    def get_search_index(index_name: str) -> Dict[str, Any]:
        """
        Retrieve a search index metadata.
        
        Args:
            index_name: Name of the index
            
        Returns:
            Dict: Search index data or empty dict if not found
        """
        key = f"{VectorMetadataManager.INDEX_PREFIX}{index_name}"
        result = MetaDataManager.get(key, {})
        return result if result is not None else {}
    
    @staticmethod
    def update_search_stats(stats_name: str, stats_data: Dict[str, Any]) -> bool:
        """
        Update search statistics.
        
        Args:
            stats_name: Name of the statistics category
            stats_data: Dictionary containing statistics data
            
        Returns:
            bool: Success status
        """
        key = f"{VectorMetadataManager.STATS_PREFIX}{stats_name}"
        return MetaDataManager.set(
            key=key,
            value=stats_data,
            description=f"Vector search statistics for {stats_name}"
        )
    
    @staticmethod
    def get_search_stats(stats_name: str) -> Dict[str, Any]:
        """
        Retrieve search statistics.
        
        Args:
            stats_name: Name of the statistics category
            
        Returns:
            Dict: Statistics data or empty dict if not found
        """
        key = f"{VectorMetadataManager.STATS_PREFIX}{stats_name}"
        result = MetaDataManager.get(key, {})
        return result if result is not None else {}
    
    @staticmethod
    @transaction.atomic
    def store_vector_batch_metadata(
        documents: List[Document],
        batch_name: str
    ) -> bool:
        """
        Store metadata for a batch of vector documents.
        This method efficiently stores metadata for multiple documents.
        
        Args:
            documents: List of Langchain Document objects
            batch_name: Name identifier for this batch of documents
            
        Returns:
            bool: Success status
        """
        try:
            # Create batch metadata entry
            batch_meta = {
                "name": batch_name,
                "document_count": len(documents),
                "created_at": MetaDataManager.get("current_time", "")
            }
            
            batch_success = MetaDataManager.set(
                key=f"vector_batch_{batch_name}",
                value=batch_meta,
                description=f"Metadata for document batch {batch_name}"
            )
            
            # Store individual document metadata
            for i, doc in enumerate(documents):
                doc_id = f"{batch_name}_{i}"
                
                # Extract metadata from document
                doc_metadata = doc.metadata.copy() if hasattr(doc, 'metadata') else {}
                
                # Add additional metadata
                doc_metadata["batch"] = batch_name
                doc_metadata["doc_index"] = i
                doc_metadata["content_length"] = len(doc.page_content)
                
                # Store metadata
                VectorMetadataManager.store_document_metadata(
                    doc_id=doc_id,
                    metadata=doc_metadata
                )
            
            return batch_success
        except Exception as e:
            logger.error(f"Error storing batch metadata: {str(e)}")
            return False
    
    @staticmethod
    def find_documents_by_metadata(criteria: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Find documents based on metadata criteria.
        This performs a database query rather than a vector search.
        
        Args:
            criteria: Dictionary of metadata criteria to match
            
        Returns:
            List of matching document metadata
        """
        try:
            from .models import MetaData
            
            # Get all document metadata entries
            doc_metadata_entries = MetaData.objects.filter(
                key__startswith=VectorMetadataManager.DOC_PREFIX
            )
            
            # Filter based on criteria
            results = []
            for entry in doc_metadata_entries:
                metadata = entry.get_json()
                if metadata is None:
                    continue
                    
                # Check if all criteria match
                matches = True
                for key, value in criteria.items():
                    if key not in metadata or metadata[key] != value:
                        matches = False
                        break
                        
                if matches:
                    results.append({
                        "doc_id": entry.key.replace(VectorMetadataManager.DOC_PREFIX, ""),
                        "metadata": metadata
                    })
            
            return results
        except Exception as e:
            logger.error(f"Error finding documents by metadata: {str(e)}")
            return []
    
    @staticmethod
    def enhance_vector_search(
        question: str,
        k: int = 3,
        metadata_filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Enhanced vector search using separate metadata.
        
        Args:
            question: Search query
            k: Number of results
            metadata_filters: Optional metadata criteria to filter results
            
        Returns:
            Dict containing search results and enhanced metadata
        """
        try:
            # Get basic search results
            vector_store = RAGUtils.get_vector_store()
            search_results = vector_store.similarity_search(question, k=k)
            
            # Process results as usual
            base_results = RAGUtils.process_search_results(search_results)
            
            # Enhance with additional metadata
            enhanced_metadata = []
            for i, result in enumerate(search_results):
                # Try to identify the document ID
                doc_id = None
                if hasattr(result, 'id'):
                    doc_id = result.id
                elif 'id' in result.metadata:
                    doc_id = result.metadata['id']
                
                # If we have a doc ID, get its full metadata
                if doc_id:
                    enhanced_meta = VectorMetadataManager.get_document_metadata(doc_id)
                    if enhanced_meta:
                        enhanced_metadata.append({
                            "doc_id": doc_id,
                            "position": i,
                            "score": getattr(result, 'score', None),
                            "metadata": enhanced_meta
                        })
            
            # Combine results
            return {
                "context": base_results["context"],
                "image_paths": base_results["image_paths"],
                "enhanced_metadata": enhanced_metadata
            }
        except Exception as e:
            logger.error(f"Error in enhanced vector search: {str(e)}")
            # Fall back to basic results
            return RAGUtils.get_rag_context(question, k)