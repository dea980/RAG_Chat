from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from .models import User, Chat, RagData, SearchLog
from .serializers import UserSerializer, ChatSerializer, RagDataSerializer, SearchLogSerializer
import uuid

class ModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create()
        self.rag_data = RagData.objects.create(
            data_text="Test data",
            image_urls=["http://example.com/image.jpg"]
        )
        self.chat = Chat.objects.create(
            user=self.user,
            question_text="Test question",
            response_text="Test response",
            data=self.rag_data
        )
        self.search_log = SearchLog.objects.create(
            question=self.chat,
            data=self.rag_data
        )

    def test_user_creation(self):
        """Test user creation and ID generation"""
        self.assertIsNotNone(self.user.user_id)
        self.assertEqual(len(self.user.user_id), 16)
        self.assertIsInstance(self.user.uuid, uuid.UUID)

    def test_rag_data_creation(self):
        """Test RagData model"""
        self.assertEqual(self.rag_data.data_text, "Test data")
        self.assertEqual(self.rag_data.image_urls, ["http://example.com/image.jpg"])

    def test_chat_creation(self):
        """Test Chat model"""
        self.assertEqual(self.chat.question_text, "Test question")
        self.assertEqual(self.chat.response_text, "Test response")
        self.assertEqual(self.chat.user, self.user)
        self.assertEqual(self.chat.data, self.rag_data)

    def test_search_log_creation(self):
        """Test SearchLog model"""
        self.assertEqual(self.search_log.question, self.chat)
        self.assertEqual(self.search_log.data, self.rag_data)

class SerializerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create()
        self.rag_data = RagData.objects.create(
            data_text="Test data",
            image_urls=["http://example.com/image.jpg"]
        )
        self.chat = Chat.objects.create(
            user=self.user,
            question_text="Test question",
            response_text="Test response",
            data=self.rag_data
        )
        self.search_log = SearchLog.objects.create(
            question=self.chat,
            data=self.rag_data
        )

    def test_user_serializer(self):
        """Test UserSerializer"""
        serializer = UserSerializer(self.user)
        self.assertIn('user_id', serializer.data)
        self.assertIn('uuid', serializer.data)
        self.assertIn('created_datetime', serializer.data)

    def test_rag_data_serializer(self):
        """Test RagDataSerializer"""
        serializer = RagDataSerializer(self.rag_data)
        self.assertEqual(serializer.data['data_text'], "Test data")
        self.assertEqual(serializer.data['image_urls'], ["http://example.com/image.jpg"])

    def test_chat_serializer(self):
        """Test ChatSerializer"""
        serializer = ChatSerializer(self.chat)
        self.assertEqual(serializer.data['question_text'], "Test question")
        self.assertEqual(serializer.data['response_text'], "Test response")

class URLRedirectTests(TestCase):
    def test_root_url_redirect(self):
        """Test that the root URL redirects to the chat API endpoint"""
        response = self.client.get('/', follow=False)
        self.assertEqual(response.status_code, 302)  # Temporary redirect
        self.assertEqual(response['Location'], '/api/v1/triple/chat/')

from unittest.mock import patch

class ChatAPIViewTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create()
        self.chat_url = reverse('chat-create')

    @patch('chat.views.ChatOpenAI')
    @patch('chat.views.ChatPromptTemplate')
    def test_create_chat_success(self, mock_prompt, mock_chat):
        """Test successful chat creation"""
        # Mock the chain
        mock_chain = mock_prompt.from_template.return_value
        mock_chain.__or__ = lambda self, other: mock_chain
        mock_chain.invoke.return_value = "Test response"
        
        data = {"topic": "Test topic"}
        response = self.client.post(self.chat_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('response', response.data)
        self.assertIn('chat_id', response.data)

    def test_create_chat_no_topic(self):
        """Test chat creation with no topic"""
        data = {}
        response = self.client.post(self.chat_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    @patch('chat.views.ChatOpenAI')
    @patch('chat.views.ChatPromptTemplate')
    def test_rate_limiting(self, mock_prompt, mock_chat):
        """Test rate limiting"""
        # Mock the chain
        mock_chain = mock_prompt.from_template.return_value
        mock_chain.__or__ = lambda self, other: mock_chain
        mock_chain.invoke.return_value = "Test response"

        # Clear cache before starting the test
        from django.core.cache import cache
        cache.clear()

        # Test that we can make 5 successful requests
        for _ in range(5):
            response = self.client.post(self.chat_url, {"topic": "test"}, format='json')
            self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Test that the 6th request is rate limited
        response = self.client.post(self.chat_url, {"topic": "test"}, format='json')
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

        # Wait for rate limit to reset (in a real scenario, we'd wait 60 seconds)
        from django.core.cache import cache
        cache.clear()  # Clear the rate limiting cache

        # Test that we can make another request after clearing the cache
        response = self.client.post(self.chat_url, {"topic": "test"}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
