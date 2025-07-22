import json
import redis
from django.conf import settings
from datetime import datetime
import logging
from typing import Optional, Dict, List, Any
from redis.connection import ConnectionPool

logger = logging.getLogger(__name__)

class RedisConnectionManager:
    _instance = None
    _pool = None

    @classmethod
    def get_instance(cls) -> 'RedisConnectionManager':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.initialize_pool()

    def initialize_pool(self) -> None:
        """Initialize Redis connection pool"""
        try:
            if self._pool is None:
                self._pool = ConnectionPool(
                    host=settings.REDIS_HOST,
                    port=settings.REDIS_PORT,
                    db=settings.REDIS_MESSAGE_DB,
                    decode_responses=True,
                    socket_timeout=5,
                    retry_on_timeout=True,
                    max_connections=10
                )
                logger.info("Redis connection pool initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Redis connection pool: {str(e)}")
            raise

    def get_connection(self) -> redis.Redis:
        """Get Redis connection from pool"""
        try:
            connection = redis.Redis(connection_pool=self._pool)
            connection.ping()
            return connection
        except redis.ConnectionError as e:
            logger.error(f"Failed to get Redis connection: {str(e)}")
            raise

class RedisMessageManager:
    def __init__(self):
        """Initialize Redis message manager with connection pool"""
        try:
            self.connection_manager = RedisConnectionManager.get_instance()
            self.redis_client = self.connection_manager.get_connection()
            logger.info("Redis message manager initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Redis message manager: {str(e)}")
            raise

    def _get_message_key(self, user_id: str) -> str:
        """Generate Redis key for user messages"""
        return f"chat_messages:{user_id}"

    def _handle_redis_error(self, operation: str, error: Exception) -> None:
        """Centralized error handling for Redis operations"""
        logger.error(f"Redis error during {operation}: {str(error)}")
        try:
            # Attempt to get a fresh connection
            self.redis_client = self.connection_manager.get_connection()
        except Exception as e:
            logger.error(f"Failed to reconnect to Redis: {str(e)}")
            raise

    def save_message(self, user_id: str, message_data: Dict[str, Any]) -> bool:
        """Save a chat message to Redis with error handling and retry"""
        if not user_id:
            logger.error("Cannot save message: user_id is required")
            return False

        retries = 3
        while retries > 0:
            try:
                message_key = self._get_message_key(user_id)
                
                # Add timestamp if not present
                if 'timestamp' not in message_data:
                    message_data['timestamp'] = datetime.now().isoformat()
                
                # Convert message to JSON string
                message_json = json.dumps(message_data)
                
                # Add message to list and set expiry
                pipeline = self.redis_client.pipeline()
                pipeline.rpush(message_key, message_json)
                pipeline.expire(message_key, settings.REDIS_MESSAGE_TTL)
                pipeline.execute()
                
                logger.debug(f"Successfully saved message for user {user_id}")
                return True

            except redis.RedisError as e:
                retries -= 1
                self._handle_redis_error("save_message", e)
                if retries == 0:
                    return False

        return False

    def get_messages(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve chat messages for a user with error handling"""
        if not user_id:
            logger.error("Cannot get messages: user_id is required")
            return []

        retries = 3
        while retries > 0:
            try:
                message_key = self._get_message_key(user_id)
                
                # Get all messages
                messages = self.redis_client.lrange(message_key, 0, -1)
                
                # Parse JSON strings to objects
                parsed_messages = []
                for msg in messages:
                    try:
                        parsed_messages.append(json.loads(msg))
                    except json.JSONDecodeError as e:
                        logger.error(f"Error parsing message JSON: {str(e)}")
                        continue
                
                # Sort by timestamp descending and limit
                sorted_messages = sorted(
                    parsed_messages,
                    key=lambda x: x.get('timestamp', ''),
                    reverse=True
                )
                
                logger.debug(f"Retrieved {len(sorted_messages)} messages for user {user_id}")
                return sorted_messages[:limit]

            except redis.RedisError as e:
                retries -= 1
                self._handle_redis_error("get_messages", e)
                if retries == 0:
                    return []

        return []

    def clear_messages(self, user_id: str) -> bool:
        """Delete all messages for a user with error handling"""
        if not user_id:
            logger.error("Cannot clear messages: user_id is required")
            return False

        retries = 3
        while retries > 0:
            try:
                message_key = self._get_message_key(user_id)
                self.redis_client.delete(message_key)
                logger.debug(f"Successfully cleared messages for user {user_id}")
                return True

            except redis.RedisError as e:
                retries -= 1
                self._handle_redis_error("clear_messages", e)
                if retries == 0:
                    return False

        return False

    def check_connection(self) -> bool:
        """Check Redis connection health"""
        try:
            return bool(self.redis_client.ping())
        except redis.RedisError:
            return False

    def get_connection_info(self) -> Dict[str, Any]:
        """Get Redis connection information for monitoring"""
        try:
            info = self.redis_client.info()
            return {
                'connected_clients': info.get('connected_clients', 0),
                'used_memory': info.get('used_memory_human', '0B'),
                'total_connections_received': info.get('total_connections_received', 0),
                'total_commands_processed': info.get('total_commands_processed', 0)
            }
        except redis.RedisError as e:
            logger.error(f"Failed to get Redis info: {str(e)}")
            return {}

    def cleanup_expired_messages(self) -> int:
        """Clean up expired messages and return count of cleaned messages"""
        try:
            pattern = "chat_messages:*"
            cleaned = 0
            for key in self.redis_client.scan_iter(pattern):
                if not self.redis_client.ttl(key):
                    self.redis_client.delete(key)
                    cleaned += 1
            logger.info(f"Cleaned up {cleaned} expired message sets")
            return cleaned
        except redis.RedisError as e:
            logger.error(f"Failed to cleanup expired messages: {str(e)}")
            return 0

    def set_session(self, user_id: str) -> bool:
        """Set or update a user session in Redis"""
        # 먼저 사용자가 데이터베이스에 존재하는지 확인
        from .models import User
        
        try:
            # 데이터베이스에서 사용자 조회
            try:
                user_exists = User.objects.filter(user_id=user_id).exists()
                if not user_exists:
                    logger.warning(f"Attempted to set session for non-existent user: {user_id}")
                    return False
            except Exception as db_error:
                logger.error(f"Database error when checking user existence: {str(db_error)}")
                # 데이터베이스 오류가 발생해도 세션 설정 계속 진행
            
            # Redis에 세션 설정
            session_key = f"user_session:{user_id}"
            pipeline = self.redis_client.pipeline()
            pipeline.set(session_key, "active")
            pipeline.expire(session_key, settings.SESSION_TIMEOUT)
            pipeline.execute()
            logger.debug(f"Session set for user {user_id}")
            return True
        except redis.RedisError as e:
            logger.error(f"Failed to set session: {str(e)}")
            return False

    def check_session(self, user_id: str) -> bool:
        """Check if a user session is active"""
        try:
            session_key = f"user_session:{user_id}"
            return bool(self.redis_client.exists(session_key))
        except redis.RedisError as e:
            logger.error(f"Failed to check session: {str(e)}")
            return False

    def end_session(self, user_id: str) -> bool:
        """End a user session in Redis"""
        try:
            session_key = f"user_session:{user_id}"
            self.redis_client.delete(session_key)
            self.clear_messages(user_id)
            logger.debug(f"Session ended for user {user_id}")
            return True
        except redis.RedisError as e:
            logger.error(f"Failed to end session: {str(e)}")
            return False

    def get_active_sessions(self) -> List[str]:
        """Get list of active session user IDs"""
        try:
            active_sessions = []
            for key in self.redis_client.scan_iter("user_session:*"):
                user_id = key.split(":", 1)[1]
                active_sessions.append(user_id)
            return active_sessions
        except redis.RedisError as e:
            logger.error(f"Failed to get active sessions: {str(e)}")
            return []