from django.test import TestCase
import uuid

from ..models import User, Chat, RagData, SearchLog


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
        self.assertTrue(self.user.user_id.startswith("U"))
        self.assertEqual(len(self.user.user_id), 13)  # U + 4 prefix + 0001 + 4 suffix
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
