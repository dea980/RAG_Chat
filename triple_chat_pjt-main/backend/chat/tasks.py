from celery import shared_task
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
from .models import User, Chat
from .redis_manager import RedisMessageManager
import logging
import uuid

logger = logging.getLogger(__name__)

@shared_task
def check_session_expiry():
    """
    Check for expired sessions and clean up associated data in both Redis and database
    """
    try:
        redis_manager = RedisMessageManager()
        processed_count = 0
        
        # Get active sessions from Redis
        active_sessions = redis_manager.get_active_sessions()
        logger.info(f"Found {len(active_sessions)} active Redis sessions")
        
        # Get the expiry threshold
        expiry_threshold = timezone.now() - timedelta(seconds=settings.SESSION_TIMEOUT)
        
        # Find inactive users that haven't been marked as expired
        # Using the last_activity field to check for inactivity
        expired_users = User.objects.filter(
            expired_datetime__isnull=True,
            last_activity__lt=expiry_threshold
        )
        
        logger.info(f"Found {expired_users.count()} expired users in database")
        
        # Process expired users
        for user in expired_users:
            try:
                # End Redis session if exists
                session_uuid = str(user.uuid)
                if session_uuid in active_sessions:
                    redis_manager.end_session(session_uuid)
                    logger.debug(f"Ended Redis session for user {session_uuid}")
                
                # Clear chat messages
                redis_manager.clear_messages(session_uuid)
                logger.debug(f"Cleared messages for user {session_uuid}")
                
                # Mark user as expired in database
                user.expired_datetime = timezone.now()
                user.save()
                logger.debug(f"Marked user {session_uuid} as expired in database")
                
                processed_count += 1
                
            except Exception as e:
                logger.error(f"Error processing user {user.uuid}: {str(e)}")
                continue
        
        # Check for any orphaned Redis sessions
        for session_uuid in active_sessions:
            try:
                user = User.objects.get(uuid=session_uuid)
                # Only check if the user is already marked as expired since last_activity doesn't exist
                if user.expired_datetime:
                    redis_manager.end_session(session_uuid)
                    logger.debug(f"Cleaned up orphaned Redis session for user {session_uuid}")
                    processed_count += 1
            except User.DoesNotExist:
                redis_manager.end_session(session_uuid)
                logger.debug(f"Cleaned up orphaned Redis session for non-existent user {session_uuid}")
                processed_count += 1
        
        if processed_count > 0:
            logger.info(f"Session cleanup completed. Processed {processed_count} sessions/users.")
        else:
            logger.debug("No expired sessions found.")
            
        # 오래된 만료 사용자 정리 (30일 이상 지난 경우)
        old_expiry_threshold = timezone.now() - timedelta(days=30)
        old_expired_users = User.objects.filter(
            expired_datetime__lt=old_expiry_threshold
        )
        
        if old_expired_users.exists():
            count = old_expired_users.count()
            old_expired_users.delete()
            logger.info(f"Deleted {count} users that were expired for more than 30 days")
        
    except Exception as e:
        logger.error(f"Error in session cleanup task: {str(e)}")
        raise