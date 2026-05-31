import logging
import os
import threading

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class ChatConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "chat"

    def ready(self):
        """Initialize system components when the app is ready."""
        try:
            from .utils import MetaDataManager
            logger.info("Initializing system metadata...")
            MetaDataManager.initialize_system_metadata()
            logger.info("System metadata initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing metadata: {str(e)}")

        # Warm up the ONNX reranker in a background thread so the first user
        # request doesn't pay the 60s model-conversion cost.
        if os.getenv("RERANKER_ENABLED", "0") == "1":
            threading.Thread(
                target=self._warm_reranker, daemon=True, name="reranker-warmup",
            ).start()

    @staticmethod
    def _warm_reranker():
        try:
            from .providers import provider_manager
            logger.info("reranker warmup: loading model...")
            r = provider_manager.get_reranker()
            if r is None:
                logger.warning("reranker warmup: get_reranker returned None")
                return
            r.score("warmup", ["dummy text"])
            logger.info("reranker warmup: ready")
        except Exception as exc:
            logger.exception(f"reranker warmup failed: {exc!r}")
