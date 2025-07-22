import requests
import streamlit as st
import os
import logging
import time
from datetime import datetime
# Removed cookie controller as we're using sessions instead

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Use consistent API URL format between frontend and backend
API_BASE_URL = os.getenv("BACKEND_URL", "http://localhost:8000") + "/api/v1/triple"
def load_phone_data():
    """
    Call the backend to load and process the phone data from xlsx file.
    Returns True if successful, False otherwise.
    """
    try:
        response = requests.post(
            f"{API_BASE_URL}/chat-rag/",
            json={"mode": 2}  # mode 2 for xlsx processing
        )
        response.raise_for_status()
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        st.error(f"Failed to load phone data: {e}")
        logger.error(f"Error loading phone data: {e}")
        return False
        

def fetch_user_id(old_user_id):
    """
    Call the backend to create or retrieve a user id.
    This function is meant to be called when the application loads or needs to refresh the session.
    """
    try:
        logger.info(f"Fetching user ID - Old User ID: {old_user_id}")
        
        # Create request payload
        payload = {}
        if old_user_id:
            payload["user_id"] = old_user_id
            
        # Send request with user_id in the JSON payload instead of cookies
        response = requests.post(
            f"{API_BASE_URL}/chat-user/",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        logger.info(f"User API Response Status: {response.status_code}")
        response.raise_for_status()
        
        if response.status_code == 200:
            response_data = response.json()
            logger.info(f"User API Response Data: {response_data}")
            user_id = response_data.get('user_id')
            if user_id:
                # Update Redis session directly
                try:
                    from datetime import datetime
                    import redis
                    
                    # Get Redis connection from app.py's configuration
                    redis_host = os.getenv("REDIS_HOST", "localhost")
                    redis_port = int(os.getenv("REDIS_PORT", "6379"))
                    session_timeout = int(os.getenv("SESSION_TIMEOUT", "300"))
                    
                    redis_client = redis.StrictRedis(
                        host=redis_host,
                        port=redis_port,
                        decode_responses=True
                    )
                    
                    # Set session in Redis
                    session_key = f"user_session:{user_id}"
                    redis_client.setex(
                        session_key,
                        session_timeout,
                        datetime.now().isoformat()
                    )
                    logger.info(f"Successfully set session for {user_id} in Redis")
                except Exception as e:
                    logger.error(f"Error setting Redis session: {e}")
                
                st.session_state.user_id = user_id
                st.session_state.last_activity = time.time()
                return user_id
            else:
                logger.error("No user_id in response")
                return None
    except requests.Timeout:
        logger.error("Request timed out")
        st.error("Request timed out. Please try again.")
        return None
    except requests.RequestException as e:
        logger.error(f"API request failed: {e}")
        st.error("Failed to connect to the server. Please try again.")
        return None
    except (ValueError, KeyError) as e:
        logger.error(f"Error processing response: {e}")
        st.error("Error processing server response. Please try again.")
        return None