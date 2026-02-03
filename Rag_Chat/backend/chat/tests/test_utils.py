import unittest
from unittest.mock import patch, MagicMock
from django.test import TestCase

from ..utils import RAGUtils
from langchain.schema import Document


class RAGUtilsTestCase(TestCase):
    """
    Test case for the RAGUtils utility class
    """
    
    @patch('backend.chat.utils.provider_manager.get_vector_store')
    def test_get_vector_store(self, mock_get_vector_store):
        """Test the get_vector_store method"""
        mock_vector_store = MagicMock()
        mock_get_vector_store.return_value = mock_vector_store
        
        # Call the method
        result = RAGUtils.get_vector_store()
        
        # Assertions
        mock_get_vector_store.assert_called_once()
        self.assertEqual(result, mock_vector_store)
    
    def test_process_search_results(self):
        """Test the process_search_results method"""
        # Create test data
        doc1 = Document(page_content="Test content 1", metadata={"image_path": "image1.png"})
        doc2 = Document(page_content="Test content 2", metadata={})
        doc3 = Document(page_content="Test content 3", metadata={"image_path": "image2.png"})
        
        search_results = [doc1, doc2, doc3]
        
        # Call the method
        result = RAGUtils.process_search_results(search_results)
        
        # Assertions
        expected_context = "Test content 1\nTest content 2\nTest content 3"
        expected_image_paths = ["image1.png", "image2.png"]
        
        self.assertEqual(result["context"], expected_context)
        self.assertEqual(result["image_paths"], expected_image_paths)
    
    @patch('backend.chat.utils.RAGUtils.get_vector_store')
    def test_get_rag_context(self, mock_get_vector_store):
        """Test the get_rag_context method"""
        # Setup mocks
        mock_vector_store = MagicMock()
        mock_get_vector_store.return_value = mock_vector_store
        
        doc1 = Document(page_content="Test content 1", metadata={"image_path": "image1.png"})
        mock_vector_store.similarity_search.return_value = [doc1]
        
        # Call the method
        result = RAGUtils.get_rag_context("test question")
        
        # Assertions
        mock_get_vector_store.assert_called_once()
        mock_vector_store.similarity_search.assert_called_once_with("test question", k=3)
        
        self.assertEqual(result["context"], "Test content 1")
        self.assertEqual(result["image_paths"], ["image1.png"])
    
    @patch('backend.chat.utils.provider_manager.create_vector_store_from_documents')
    def test_create_vector_store_from_documents(self, mock_create_vector_store):
        """Test the create_vector_store_from_documents method"""
        mock_vector_store = MagicMock()
        mock_vector_store._collection.count.return_value = 5
        mock_create_vector_store.return_value = mock_vector_store
        
        # Test documents
        documents = [
            Document(page_content="Test content 1", metadata={}),
            Document(page_content="Test content 2", metadata={})
        ]
        
        # Call the method
        result = RAGUtils.create_vector_store_from_documents(documents)
        
        # Assertions
        mock_create_vector_store.assert_called_once_with(documents)
        self.assertEqual(result, mock_vector_store)


if __name__ == '__main__':
    unittest.main()
