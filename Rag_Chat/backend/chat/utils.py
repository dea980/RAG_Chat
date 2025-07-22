from django.conf import settings
from typing import Dict, Any, List, Optional, Union
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.schema import Document
import logging
from openai import OpenAIError
import os
import openai
import json
from django.utils.timezone import now

# Set API key directly for OpenAI
# API_KEY = ""
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
                "gpt-4o-mini",
                "Current LLM model in use"
            )
        
        # Embedding model info
        if not MetaData.objects.filter(key="embedding_model").exists():
            MetaDataManager.set(
                "embedding_model",
                "text-embedding-ada-002",
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
    def get_vector_store(embedding_model="text-embedding-ada-002"):
        """Get Chroma vector store with specified embedding model"""
        try:
            embeddings = OpenAIEmbeddings(model=embedding_model, openai_api_key=API_KEY)
            vector_store = Chroma(
                persist_directory=settings.VECTOR_STORE_PATH,
                embedding_function=embeddings
            )
            return vector_store
        except OpenAIError as e:
            logger.error(f"OpenAI API error in get_vector_store: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error creating vector store: {str(e)}")
            raise
    
    @staticmethod
    def process_search_results(search_results):
        """Process search results to extract context and image paths"""
        context = "\n".join([doc.page_content for doc in search_results])
        image_paths = []
        
        for result in search_results:
            if "image_path" in result.metadata:
                image_paths.append(result.metadata["image_path"])
                
        return {
            "context": context,
            "image_paths": image_paths
        }
    
    @staticmethod
    def get_rag_context(question: str, k: int = 3) -> Dict[str, Any]:
        """
        Retrieve RAG context for a given question with improved error handling
        """
        try:
            vector_store = RAGUtils.get_vector_store()
            search_results = vector_store.similarity_search(question, k=k)
            return RAGUtils.process_search_results(search_results)
        except OpenAIError as e:
            logger.error(f"OpenAI API error in get_rag_context: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error in get_rag_context: {str(e)}")
            return {
                "context": "",
                "image_paths": []
            }
    
    @staticmethod
    def create_vector_store_from_documents(documents: List[Document], embedding_model="text-embedding-ada-002"):
        """Create and persist a vector store from documents"""
        try:
            embeddings = OpenAIEmbeddings(model=embedding_model, openai_api_key=API_KEY)
            vector_store = Chroma.from_documents(
                documents=documents,
                embedding=embeddings,
                persist_directory=settings.VECTOR_STORE_PATH
            )
            logger.info(f"Vector store created with {vector_store._collection.count()} documents")
            return vector_store
        except Exception as e:
            logger.error(f"Error creating vector store: {str(e)}")
            raise