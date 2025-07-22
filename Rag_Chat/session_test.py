import requests
import time
import redis
import json
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
API_BASE_URL = "http://localhost:8000/api/v1/triple"
REDIS_HOST = "localhost"
REDIS_PORT = 6379
SESSION_DURATION = 30  # seconds to wait between session checks

def test_session_persistence():
    """
    Test if sessions persist correctly by:
    1. Creating a user session
    2. Waiting for a period
    3. Checking if the session is still active
    """
    logger.info("Starting session persistence test")
    
    # Create a new user session
    try:
        response = requests.post(
            f"{API_BASE_URL}/chat-user/",
            json={}  # Don't need username parameter
        )
        response.raise_for_status()
        user_data = response.json()
        user_id = user_data.get('user_id')
        
        if not user_id:
            logger.error("No user_id returned from API")
            return False
            
        logger.info(f"Created new user session with ID: {user_id}")
        
        # Check Redis for the session
        try:
            redis_client = redis.StrictRedis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=1,  # Use REDIS_MESSAGE_DB from settings
                decode_responses=True
            )
            
            session_key = f"user_session:{user_id}"
            if redis_client.exists(session_key):
                ttl = redis_client.ttl(session_key)
                logger.info(f"Session exists in Redis with TTL: {ttl} seconds")
            else:
                logger.error("Session not found in Redis")
                return False
                
            # Wait for a period to test session persistence
            logger.info(f"Waiting for {SESSION_DURATION} seconds...")
            time.sleep(SESSION_DURATION)
            # Check if session still exists
            if redis_client.exists(session_key):
                ttl = redis_client.ttl(session_key)
                logger.info(f"Session still exists after {SESSION_DURATION} seconds with TTL: {ttl} seconds")
                
                # For this test, we only care if the session persists in Redis
                # We'll consider the test passed if the session exists and has a valid TTL
                if ttl > 0:
                    logger.info("Session persistence test passed - session exists with valid TTL")
                    return True
                else:
                    logger.error(f"Session exists but has invalid TTL: {ttl}")
                    return False
            else:
                logger.error(f"Session expired after {SESSION_DURATION} seconds")
                return False
                
        except redis.RedisError as e:
            logger.error(f"Redis error: {e}")
            return False
            
    except requests.RequestException as e:
        logger.error(f"API request error: {e}")
        return False
        
    return True

if __name__ == "__main__":
    if test_session_persistence():
        logger.info("✅ TEST PASSED: Session persistence is working correctly")
    else:
        logger.error("❌ TEST FAILED: Session persistence issue detected")