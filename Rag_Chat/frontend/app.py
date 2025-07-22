import streamlit as st
import redis
import threading
import requests
import json
import logging
import os
import time
from datetime import datetime, timedelta
from api import fetch_user_id
from typing import Optional, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
# Use consistent Redis URL format between frontend and backend
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"  # Constructed from REDIS_HOST and REDIS_PORT

API_BASE_URL = os.getenv("BACKEND_URL", "http://localhost:8000") + "/api/v1/triple"

# Use the same session timeout as backend (from .env)
SESSION_TIMEOUT = int(os.getenv("SESSION_TIMEOUT", "300"))  # 5 minutes in seconds (matching backend)
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds
INACTIVITY_CHECK_INTERVAL = 60  # 60 seconds

# Django
# Use consistent URL from environment variables
BACKEND_HOST = os.getenv("BACKEND_HOST", "localhost")
BACKEND_PORT = os.getenv("BACKEND_PORT", "8000")
STATIC_IMAGE_URL = f"http://{BACKEND_HOST}:{BACKEND_PORT}/static/images/"

# Create Redis manager class
class RedisManager:
    def get_client(self):
        return redis_client

# Initialize Redis connection with error handling
try:
    redis_client = redis.StrictRedis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        decode_responses=True,
        socket_timeout=30,  # Increased timeout for pub/sub operations
        socket_connect_timeout=10,  # Separate connection timeout
        socket_keepalive=True,  # Keep connection alive
        health_check_interval=15  # Check connection health periodically
    )
    redis_client.ping()  # Test connection
    # Create the redis_manager instance
    redis_manager = RedisManager()
except redis.ConnectionError as e:
    logger.error(f"Failed to connect to Redis: {e}")
    st.error("Failed to connect to session management service. Please try again later.")
    st.stop()

def init_session():
    """Initialize session state variables"""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "session_expired" not in st.session_state:
        st.session_state.session_expired: bool = False
    # Username is not used in this application
    if "user_id" not in st.session_state:
        st.session_state.user_id: Optional[str] = None
    if "last_activity" not in st.session_state:
        st.session_state.last_activity: Optional[float] = None

def check_session_active() -> bool:
    """Check if the current session is active in Redis"""
    if not st.session_state.user_id:
        return False
    try:
        redis_client = redis_manager.get_client()
        if not redis_client:
            return False
        return bool(redis_client.get(f"user_session:{st.session_state.user_id}"))
    except redis.RedisError as e:
        logger.error(f"Failed to check session: {e}")
        return False

def listen_to_redis():
    """Enhanced Redis pub/sub listener with automatic reconnection and improved resilience"""
    consecutive_timeouts = 0
    max_consecutive_timeouts = 5  # Increased maximum timeouts
    base_delay = RETRY_DELAY
    
    while True:
        pubsub = None
        try:
            redis_client = redis_manager.get_client()
            if not redis_client:
                logger.warning("No Redis client available, retrying in 5 seconds...")
                time.sleep(base_delay)
                continue

            # Test connection health before subscribing
            if not redis_client.ping():
                logger.warning("Redis connection failed ping test, reconnecting...")
                time.sleep(base_delay)
                continue
                
            logger.info("Connecting to Redis pub/sub...")
            pubsub = redis_client.pubsub(ignore_subscribe_messages=True)
            pubsub.subscribe("session_expired", "chat_messages")
            
            # Reset timeout counter and delay on successful connection
            consecutive_timeouts = 0
            current_delay = base_delay
            
            logger.info("Listening for Redis messages...")
            
            # Use get_message with timeout instead of listen() for better control
            while True:
                # Check connection health periodically
                if consecutive_timeouts > 0 and consecutive_timeouts % 3 == 0:
                    if not redis_client.ping():
                        logger.warning("Redis health check failed, reconnecting...")
                        break
                        
                message = pubsub.get_message(timeout=5.0)
                if message and message["type"] == "message":
                    if message["channel"] == "session_expired":
                        st.session_state["session_expired"] = True
                        st.warning("Your session has expired. Please log in again.")
                    elif message["channel"] == "chat_messages":
                        data = json.loads(message['data'])
                        if data.get('user_id') == st.session_state.get('user_id'):
                            st.session_state.messages.append({
                                "role": "assistant",
                                "content": data.get('message', '')
                            })
                            time.sleep(0.1)  # Small delay to prevent excessive updates
                            st.rerun()
                
                # Small sleep to prevent CPU hogging when no messages
                time.sleep(0.01)
                
        except redis.TimeoutError as e:
            consecutive_timeouts += 1
            # Use exponential backoff for retries
            current_delay = min(base_delay * (2 ** (consecutive_timeouts - 1)), 30)
            logger.warning(f"Redis timeout ({consecutive_timeouts}/{max_consecutive_timeouts}): {e}")
            logger.warning(f"Retrying in {current_delay} seconds...")
            
            if consecutive_timeouts >= max_consecutive_timeouts:
                logger.error("Too many consecutive Redis timeouts, forcing reconnection...")
                consecutive_timeouts = 0  # Reset counter
                
                # Close pubsub connection if it exists
                if pubsub:
                    try:
                        pubsub.close()
                    except:
                        pass
            
            time.sleep(current_delay)
            
        except redis.ConnectionError as e:
            logger.error(f"Redis connection error: {e}")
            time.sleep(base_delay * 2)
            if pubsub:
                try:
                    pubsub.close()
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"Redis listener error: {e}")
            logger.exception("Detailed error information:")
            time.sleep(base_delay * 2)  # Longer delay on errors
            if pubsub:
                try:
                    pubsub.close()
                except:
                    pass

def update_session_activity() -> bool:
    """Update user's last activity timestamp with success confirmation and retry logic"""
    if not st.session_state.user_id:
        logger.warning("Cannot update session: no user_id in session state")
        return False

    retries = MAX_RETRIES
    retry_delay = 1  # Start with a shorter delay for this function
    
    while retries > 0:
        try:
            redis_client = redis_manager.get_client()
            if not redis_client:
                logger.warning("No Redis client available for session update")
                time.sleep(retry_delay)
                retries -= 1
                continue

            # Try to ping Redis first to verify connection
            if not redis_client.ping():
                logger.warning("Redis ping failed before session update")
                time.sleep(retry_delay)
                retries -= 1
                continue
                
            current_time = datetime.now().isoformat()
            session_key = f"user_session:{st.session_state.user_id}"
            
            # Use pipeline for atomic operations
            pipeline = redis_client.pipeline()
            pipeline.setex(
                session_key,
                SESSION_TIMEOUT,
                current_time
            )
            # Execute the pipeline and get results
            results = pipeline.execute()
            success = results[0]
            
            if success:
                st.session_state.last_activity = time.time()
                logger.debug(f"Successfully updated session activity for user {st.session_state.user_id}")
                return True
            
            logger.warning(f"Redis setex returned {success} for session update")
            
            # If Redis operation failed, try to get a fresh user ID
            if retries == 1:  # Last retry attempt
                try:
                    logger.info("Attempting to refresh user session...")
                    new_user_id = fetch_user_id(st.session_state.user_id)
                    if new_user_id:
                        logger.info(f"Successfully refreshed user session: {new_user_id}")
                        st.session_state.last_activity = time.time()
                        return True
                except Exception as refresh_error:
                    logger.error(f"Failed to refresh session: {refresh_error}")
            
            retries -= 1
            
        except redis.TimeoutError as e:
            logger.warning(f"Timeout updating session activity: {e}")
            retries -= 1
            time.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 5)  # Exponential backoff up to 5 seconds
            
        except redis.RedisError as e:
            logger.error(f"Redis error updating session: {e}")
            retries -= 1
            time.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 5)
            
        except Exception as e:
            logger.error(f"Unexpected error updating session: {e}")
            retries -= 1
            time.sleep(retry_delay)
    
    # If we've exhausted retries
    logger.error(f"Failed to update session after {MAX_RETRIES} attempts")
    return False

def send_chat_request(prompt):
    """Send chat request to backend API"""
    try:
        # Get user_id from session state
        user_id = st.session_state.get("user_id")
        if not user_id:
            logger.error("No user_id found in session state")
            st.error("Session not found. Please refresh the page.")
            return None

        # Log request details
        logger.info(f"Sending chat request - User ID: {user_id}, Prompt: {prompt}")
        
        # Make the API request using the API_BASE_URL from api.py
        request_url = f"{API_BASE_URL}/chat/"
        logger.info(f"Making request to: {request_url}")
        
        response = requests.post(
            request_url,
            json={
                "question": prompt,
                "user_id": st.session_state.get("user_id", None)  # Include user_id in JSON payload
            },
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except requests.Timeout:
        logger.error("Request timed out")
        st.error("Request timed out. Please try again.")
        return None
    except requests.RequestException as e:
        logger.error(f"API request failed: {e}")
        logger.error(f"Request details: URL={request_url}, user_id={user_id}")
        st.error("Failed to get response from chat service. Please try again.")
        return None
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        st.error("An unexpected error occurred. Please try again.")
        return None

# Initialize session state
init_session()

# Initialize or get user ID if not in session state yet
if not st.session_state.user_id:
    try:
        # Call the api.py function to get a user ID
        user_id = fetch_user_id(None)  # Pass None for new session
        if user_id:
            st.session_state.user_id = user_id
            st.session_state.last_activity = time.time()
            logger.info(f"Initialized new user session: {user_id}")
    except Exception as e:
        logger.error(f"Failed to initialize user session: {e}")

# Start Redis listener in background
thread = threading.Thread(target=listen_to_redis, daemon=True)
thread.start()

# Auto-rerun for session timeout check
if 'last_rerun' not in st.session_state:
    st.session_state.last_rerun = time.time()

current_time = time.time()
if current_time - st.session_state.last_rerun > INACTIVITY_CHECK_INTERVAL:
    st.session_state.last_rerun = current_time
    
    # Also update session activity timestamp in Redis
    if st.session_state.user_id:
        update_session_activity()
        
    time.sleep(0.1)  # Small delay to prevent excessive reruns
    st.rerun()

def check_session_timeout():
    """Check if session has timed out with retry mechanism"""
    if not st.session_state.user_id:
        # No user ID means we're already in an unauthenticated state
        logger.debug("No user_id in session state during timeout check")
        return False

    # Check last activity time locally first
    if st.session_state.last_activity:
        inactivity_time = time.time() - st.session_state.last_activity
        if inactivity_time > SESSION_TIMEOUT:
            logger.info(f"Local session timeout detected. Inactive for {inactivity_time:.1f} seconds")
            # Attempt to refresh session before marking as expired
            if update_session_activity():
                logger.info("Successfully refreshed expired session")
                return True
            else:
                logger.warning("Failed to refresh expired session, marking as expired")
                st.session_state.session_expired = True
                return False
    
    # Double-check with Redis as well
    try:
        is_active = check_session_active()
        if not is_active:
            logger.warning("Session not active in Redis despite being active locally")
            # Try to refresh it one last time
            if update_session_activity():
                logger.info("Successfully reactivated session in Redis")
                return True
            else:
                st.session_state.session_expired = True
                return False
    except Exception as e:
        logger.error(f"Error checking session in Redis: {e}")
        # If we can't check Redis, trust the local activity time
        pass
        
    return True

def load_phone_data():
    """Load phone data from backend"""
    try:
        from api import load_phone_data as api_load_phone_data
        return api_load_phone_data()
    except Exception as e:
        logger.error(f"Failed to load phone data: {e}")
        return False

# UI Components
st.title("Samsung Galaxy 25 Phone Chat Assistant")

# Session status indicator
if st.session_state.user_id:
    st.sidebar.success(f"Session active: {st.session_state.user_id}")
else:
    st.sidebar.warning("No active session")

# Admin controls in sidebar
st.sidebar.markdown("---")
st.sidebar.markdown("### Admin Controls")
if st.sidebar.button("Load Phone Data"):
    with st.sidebar.status("Loading phone data..."):
        if load_phone_data():
            st.sidebar.success("Phone data loaded successfully!")
        else:
            st.sidebar.error("Failed to load phone data. Please try again.")

# Check for session timeout
check_session_timeout()

# Chat interface
is_session_active = check_session_active()
if not st.session_state.session_expired and st.session_state.user_id and is_session_active:
    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    # Chat input
    if prompt := st.chat_input("What would you like to discuss?"):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)

        # Update session activity
        update_session_activity()

        # Get AI response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                if response_data := send_chat_request(prompt):
                    response = response_data.get("response", "Sorry, I couldn't process that.")
                    images = response_data.get("images", [])
            
                    # Response Text
                    st.write(response)
                    
                    # Response Image
                    if images:
                        st.write("🔹 Related Images:")
                        for image in images:
                            image_url = STATIC_IMAGE_URL + image + ".png"
                            st.image(image_url, use_container_width=True)
                    
                    st.session_state.messages.append({"role": "assistant", "content": response})

else:
    st.warning("Your session has expired. Please refresh the page to start a new session.")
    if st.button("Start New Session", key="main_new_session"):
        st.session_state.session_expired = False
        st.session_state.messages = []
        st.rerun()

# New session button in sidebar
if st.sidebar.button("Start New Session"):
    st.session_state.session_expired = False
    st.session_state.messages = []
    st.session_state.user_id = None
    st.session_state.last_activity = None
    st.rerun()