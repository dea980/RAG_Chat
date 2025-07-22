from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)

class ChatConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "chat"
    
    def ready(self):
        """
        Initialize system components when the app is ready
        """
        try:
            # Import here to avoid circular imports
            from .utils import MetaDataManager
            
            # Initialize system metadata
            logger.info("Initializing system metadata...")
            MetaDataManager.initialize_system_metadata()
            logger.info("System metadata initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing metadata: {str(e)}")
