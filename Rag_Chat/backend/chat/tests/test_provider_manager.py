from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from ..providers.manager import ProviderManager


class ProviderManagerChatProviderTests(SimpleTestCase):
    @patch("chat.providers.manager.ChatOpenAI")
    @override_settings(VECTOR_STORE_PATH="/tmp/test-vector-store")
    def test_ollama_chat_model_uses_openai_compatible_endpoint(self, mock_chat_openai):
        with patch.dict(
            "os.environ",
            {
                "OLLAMA_BASE_URL": "http://localhost:11434/v1",
                "OLLAMA_MODEL": "llama3.1",
                "REASONING_TEMPERATURE": "0.2",
            },
            clear=False,
        ):
            manager = ProviderManager()

            manager._create_chat_model("ollama", "REASONING")

        mock_chat_openai.assert_called_once_with(
            api_key="ollama",
            base_url="http://localhost:11434/v1",
            model="llama3.1",
            temperature=0.2,
        )

    @patch("chat.providers.manager.ChatOpenAI")
    def test_huggingface_chat_model_uses_configured_endpoint(self, mock_chat_openai):
        with patch.dict(
            "os.environ",
            {
                "HUGGINGFACE_API_KEY": "hf_test",
                "HUGGINGFACE_BASE_URL": "https://example.endpoints.huggingface.cloud/v1",
                "HUGGINGFACE_MODEL": "meta-llama/Llama-3.1-8B-Instruct",
                "GENERATION_TEMPERATURE": "0.4",
            },
            clear=False,
        ):
            manager = ProviderManager()

            manager._create_chat_model("huggingface", "GENERATION")

        mock_chat_openai.assert_called_once_with(
            api_key="hf_test",
            base_url="https://example.endpoints.huggingface.cloud/v1",
            model="meta-llama/Llama-3.1-8B-Instruct",
            temperature=0.4,
        )

    def test_embedding_config_is_separate_from_chat_selection(self):
        with patch.dict(
            "os.environ",
            {
                "EMBEDDING_PROVIDER": "huggingface",
                "EMBEDDING_MODEL": "BAAI/bge-m3",
                "REASONING_PROVIDER": "ollama",
                "GENERATION_PROVIDER": "huggingface",
            },
            clear=False,
        ):
            manager = ProviderManager()

            config = manager.get_embedding_config()

        self.assertEqual(
            config,
            {
                "provider": "huggingface",
                "model": "BAAI/bge-m3",
                "scope": "system",
                "requires_reindex": True,
            },
        )
