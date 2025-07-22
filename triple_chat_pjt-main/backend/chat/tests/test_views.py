from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch
import json

from ..models import User, Chat, RagData, SearchLog


class SearchLogAPIViewTestCase(TestCase):
    """Test case for the SearchLogAPIView"""
    
    def setUp(self):
        """Set up test data"""
        # Create test user
        self.user = User.objects.create(username="testuser")
        
        # Create test RagData
        self.rag_data = RagData.objects.create(
            data_text="Test context",
            image_urls=["image1.png", "image2.png"]
        )
        
        # Create test Chat
        self.chat = Chat.objects.create(
            user=self.user,
            question_text="Test question",
            response_text="Test response",
            data=self.rag_data
        )
        
        # Create test SearchLog
        self.search_log = SearchLog.objects.create(
            data=self.rag_data,
            question=self.chat
        )
        
        # Create API client
        self.client = APIClient()
    
    def test_get_search_logs(self):
        """Test retrieving search logs without filters"""
        url = reverse('search-logs')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['question'], self.chat.question_id)
        self.assertEqual(response.data[0]['data'], self.rag_data.data_id)
    
    def test_get_search_logs_with_user_filter(self):
        """Test retrieving search logs with user filter"""
        url = reverse('search-logs')
        response = self.client.get(url, {'user_id': self.user.user_id})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        
        # Create a different user and associated data
        other_user = User.objects.create(username="otheruser")
        other_chat = Chat.objects.create(
            user=other_user,
            question_text="Other question",
            response_text="Other response",
            data=self.rag_data
        )
        other_search_log = SearchLog.objects.create(
            data=self.rag_data,
            question=other_chat
        )
        
        # Filter by first user
        response = self.client.get(url, {'user_id': self.user.user_id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['question'], self.chat.question_id)
        
        # Filter by second user
        response = self.client.get(url, {'user_id': other_user.user_id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['question'], other_chat.question_id)
    
    @patch('backend.chat.views.SearchLog.objects.all')
    def test_handle_exception(self, mock_all):
        """Test error handling in the view"""
        # Make the query raise an exception
        mock_all.side_effect = Exception("Test exception")
        
        url = reverse('search-logs')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data['error'], "Failed to retrieve search logs")