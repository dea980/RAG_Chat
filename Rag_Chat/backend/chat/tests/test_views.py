from django.test import TestCase
from django.urls import reverse
from django.core.cache import cache
from rest_framework.test import APIClient, APITestCase
from rest_framework import status
from unittest.mock import patch, MagicMock
import json

from ..models import User, Chat, RagData, SearchLog
from ..providers import provider_manager


class SearchLogAPIViewTestCase(TestCase):
    """Test case for the SearchLogAPIView"""
    
    def setUp(self):
        """Set up test data"""
        # Create test user (post-B3 — email is USERNAME_FIELD)
        self.user = User.objects.create_user(email="testuser@triplechat.test")
        
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
        other_user = User.objects.create_user(email="otheruser@triplechat.test")
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
    
    @patch('chat.views.SearchLog.objects.all')
    def test_handle_exception(self, mock_all):
        """Test error handling in the view"""
        # Make the query raise an exception
        mock_all.side_effect = Exception("Test exception")
        
        url = reverse('search-logs')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data['error'], "Failed to retrieve search logs")


class ProviderConfigAPIViewTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

    @patch("chat.views.provider_manager.get_embedding_config")
    def test_get_returns_chat_selection_and_embedding_config(self, mock_embedding_config):
        mock_embedding_config.return_value = {
            "provider": "gemini",
            "model": "models/text-embedding-004",
            "scope": "system",
            "requires_reindex": True,
        }

        response = self.client.get(reverse("provider-config"), {"user_id": "session-1"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("selection", response.data)
        self.assertEqual(response.data["embedding"], mock_embedding_config.return_value)

    def test_post_accepts_ollama_only_combo(self):
        response = self.client.post(
            reverse("provider-config"),
            {"user_id": "session-1", "provider_combo": "ollama_only"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["selection"],
            {
                "reasoning_provider": "ollama",
                "generation_provider": "ollama",
            },
        )

    def test_post_accepts_huggingface_only_combo(self):
        response = self.client.post(
            reverse("provider-config"),
            {"user_id": "session-1", "provider_combo": "huggingface_only"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["selection"],
            {
                "reasoning_provider": "huggingface",
                "generation_provider": "huggingface",
            },
        )

    def test_post_accepts_openrouter_manual_provider(self):
        response = self.client.post(
            reverse("provider-config"),
            {
                "user_id": "session-1",
                "reasoning_provider": "openrouter",
                "generation_provider": "ollama",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["selection"],
            {
                "reasoning_provider": "openrouter",
                "generation_provider": "ollama",
            },
        )

    def test_get_default_selection(self):
        """Test default provider selection matches env-configured default"""
        from ..providers import provider_manager

        user = User.objects.create()
        response = self.client.get(
            reverse("provider-config"), {"user_id": user.user_id}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["selection"]["reasoning_provider"],
            provider_manager.reasoning_provider_name,
        )

    def test_set_combo(self):
        """Test setting a named combo persists"""
        user = User.objects.create()
        response = self.client.post(
            reverse("provider-config"),
            {
                "user_id": user.user_id,
                "provider_combo": "qwen_reasoning_gemini_generation",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["selection"]["reasoning_provider"], "qwen")
        self.assertEqual(response.data["selection"]["generation_provider"], "gemini")

        response = self.client.get(
            reverse("provider-config"), {"user_id": user.user_id}
        )
        self.assertEqual(response.data["selection"]["reasoning_provider"], "qwen")

    def test_custom_override_and_clear(self):
        """Test custom override then DELETE resets to default"""
        user = User.objects.create()
        payload = {
            "user_id": user.user_id,
            "reasoning_provider": "qwen",
            "generation_provider": "qwen",
        }
        response = self.client.post(
            reverse("provider-config"), payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["selection"]["generation_provider"], "qwen")

        response = self.client.delete(
            reverse("provider-config"),
            {"user_id": user.user_id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["selection"]["reasoning_provider"],
            provider_manager.reasoning_provider_name,
        )


class URLRedirectTests(TestCase):
    def test_root_url_redirect(self):
        """Test that the root URL redirects to the chat API endpoint"""
        response = self.client.get("/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/api/v1/triple/chat/")


class ChatAPIViewTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create()
        self.client.force_authenticate(user=self.user)
        self.chat_url = reverse("chat-create")

    @staticmethod
    def _fake_pipeline_run(ctx):
        """Minimal pipeline mock matching PipelineRunner.run signature."""
        ctx.context_text = "test context"
        ctx.response = "Test response"
        ctx.extra["rag_metadata"] = {"redacted_count": 0, "image_paths": []}
        return ctx

    @staticmethod
    def _mod_result():
        return type("R", (), {"sanitized": "test"})()

    @patch("chat.views.moderate_text")
    @patch("chat.views.PipelineRunner.run", side_effect=_fake_pipeline_run.__func__)
    def test_create_chat_success(self, mock_run, mock_mod):
        """Test successful chat creation"""
        mock_mod.return_value = self._mod_result()
        data = {"question": "Test question", "user_id": self.user.user_id}
        response = self.client.post(self.chat_url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("response", response.data)
        self.assertIn("chat_id", response.data)

    def test_create_chat_no_topic(self):
        """Test chat creation with no topic"""
        data = {}
        response = self.client.post(self.chat_url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    @patch("chat.views.ChatRateThrottle.rate", "5/minute")
    @patch("chat.views.moderate_text")
    @patch("chat.views.PipelineRunner.run", side_effect=_fake_pipeline_run.__func__)
    def test_rate_limiting(self, mock_run, mock_mod):
        """Test rate limiting"""
        mock_mod.return_value = self._mod_result()
        cache.clear()

        for _ in range(5):
            response = self.client.post(
                self.chat_url,
                {"question": "test", "user_id": self.user.user_id},
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.post(
            self.chat_url,
            {"question": "test", "user_id": self.user.user_id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

        cache.clear()

        response = self.client.post(
            self.chat_url,
            {"question": "test", "user_id": self.user.user_id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
