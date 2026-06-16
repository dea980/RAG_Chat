from django.test import TestCase

from ..models import User, Chat, RagData, SearchLog
from ..serializers import UserSerializer, ChatSerializer, RagDataSerializer, SearchLogSerializer


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
