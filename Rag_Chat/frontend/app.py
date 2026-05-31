import streamlit as st
import redis
import threading
import requests
import json
import logging
import os
import time
from datetime import datetime, timedelta
from api import fetch_user_id, get_provider_selection, set_provider_selection, upload_knowledge_files
from typing import Optional, Dict, Any
import auth as auth_mod  # B5 — session-based login
import messages_api as msgs_api  # ChatGPT-style conv/messages endpoints

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
        
        # B5 — use the authenticated requests.Session so the Django sessionid
        # cookie is sent. user_id is no longer sent in the payload; the backend
        # reads request.user from the session (B4).
        sess = auth_mod.get_session()
        # DRF SessionAuthentication enforces CSRF on non-safe methods.
        # Forward the csrftoken cookie as X-CSRFToken header — otherwise
        # Django returns 403 with `detail: "CSRF Failed: ..."` and the
        # frontend wrongly treats it as a moderation block.
        csrf_token = sess.cookies.get("csrftoken", "")
        response = sess.post(
            request_url,
            json={"question": prompt},
            headers={
                "Content-Type": "application/json",
                "X-CSRFToken": csrf_token,
                "Referer": API_BASE_URL,
            },
            # Ollama gpt-oss 첫 콜드 호출 = 60~120s. 그 다음 호출도 RAG context
            # 큰 답변은 30~60s. 180s 까지 허용.
            timeout=180,
        )
        # 403 disambiguation:
        #   - CSRF failure  → body has `detail: "CSRF Failed: ..."`, treat as error.
        #   - Moderation    → body has `blocked_words`/`categories`/`next_steps`.
        if response.status_code == 403:
            try:
                payload = response.json()
            except ValueError:
                payload = {}
            if "blocked_words" in payload or "categories" in payload:
                payload["blocked"] = True
                return payload
            # CSRF / permission / other 403 — surface as error.
            logger.error(f"chat 403 (non-moderation): {payload}")
            st.error(f"인증 또는 권한 오류 (403): {payload.get('detail', '')}")
            return None
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

# B5 — auth gate. No more silent fetch_user_id; user must sign in.
if not auth_mod.is_authenticated():
    st.title("Triple Chat — Sign in")
    auth_mod.render_login_form()
    st.stop()

# After login the backend session carries user_id; mirror it locally for the
# existing Redis-session tracking code.
if not st.session_state.user_id:
    user = auth_mod.current_user()
    if user:
        st.session_state.user_id = user["user_id"]
        st.session_state.last_activity = time.time()
        info = get_provider_selection(user["user_id"])
        if info:
            st.session_state.provider_selection = info.get("selection", {})
            st.session_state.embedding_config = info.get("embedding", {})

if st.session_state.user_id and "provider_selection" not in st.session_state:
    info = get_provider_selection(st.session_state.user_id)
    if info:
        st.session_state.provider_selection = info.get("selection", {})
        st.session_state.embedding_config = info.get("embedding", {})

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
auth_mod.render_topbar()
st.title("Samsung Galaxy 25 Phone Chat Assistant")

# Session status indicator
auth_mod.render_user_chip()

# ---------------------------------------------------------------------------
# Sidebar — Conversations list (ChatGPT-style)
# ---------------------------------------------------------------------------
if auth_mod.is_authenticated():
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 💬 대화 목록")

    if st.sidebar.button("➕ 새 대화", key="conv_new_btn", use_container_width=True):
        st.session_state["active_conversation_id"] = None
        st.session_state["messages"] = []
        st.rerun()

    convs = msgs_api.list_conversations(limit=20)
    active_id = st.session_state.get("active_conversation_id")
    if not convs:
        st.sidebar.caption("아직 대화가 없습니다. 메시지를 보내 시작하세요.")
    for c in convs:
        is_active = c["id"] == active_id
        prefix = "▸ " if is_active else "  "
        label = f"{prefix}{c['title'][:28]}"
        if st.sidebar.button(
            label,
            key=f"conv_btn_{c['id']}",
            use_container_width=True,
        ):
            st.session_state["active_conversation_id"] = c["id"]
            # Hydrate messages from server
            detail = msgs_api.get_conversation(c["id"])
            if detail:
                st.session_state["messages"] = [
                    {"role": m["role"], "content": m["content"],
                     "redacted_count": m.get("redacted_count", 0)}
                    for m in detail.get("messages", [])
                ]
            st.rerun()

    # ----- 응답 설정 (knobs) -----
    st.sidebar.markdown("---")
    with st.sidebar.expander("⚙ 응답 설정", expanded=False):
        st.session_state.setdefault("knob_top_k", 5)
        st.session_state.setdefault("knob_history_turns", 5)
        st.session_state.setdefault("knob_use_reasoning", False)

        st.session_state["knob_top_k"] = st.slider(
            "검색 청크 수 (top_k)",
            1, 20, st.session_state["knob_top_k"],
            help="LLM 컨텍스트로 넘기는 RAG 청크 수. 낮을수록 빠르나 정보 적음.",
        )
        st.session_state["knob_history_turns"] = st.slider(
            "히스토리 turn 수",
            0, 20, st.session_state["knob_history_turns"],
            help="이전 대화 중 마지막 N turn 만 LLM 에 노출. 낮을수록 빠름.",
        )
        st.session_state["knob_use_reasoning"] = st.toggle(
            "추론 단계 사용",
            value=st.session_state["knob_use_reasoning"],
            help="ON = reasoning + generation (LLM 2회, 느림, 정밀). OFF = generation 만.",
        )
        if st.button("기본값으로 초기화", key="knob_reset"):
            st.session_state["knob_top_k"] = 5
            st.session_state["knob_history_turns"] = 5
            st.session_state["knob_use_reasoning"] = False
            st.rerun()
if st.session_state.user_id:
    st.sidebar.success(f"Session active: {st.session_state.user_id}")

# Admin controls in sidebar
st.sidebar.markdown("---")
st.sidebar.markdown("### Admin Controls")
uploaded_knowledge_files = st.sidebar.file_uploader(
    "Knowledge files",
    type=["xlsx", "xls", "csv", "txt", "md", "pdf", "docx", "html", "hwp"],
    accept_multiple_files=True,
    help="Upload files to update the RAG knowledge store.",
)

if st.sidebar.button("Upload & Update Knowledge", disabled=not uploaded_knowledge_files):
    with st.sidebar.status("Uploading knowledge files..."):
        result = upload_knowledge_files(uploaded_knowledge_files)
        if result:
            processed = result.get("processed", [])
            failed = result.get("failed", [])
            if processed:
                st.sidebar.success(f"Processed {len(processed)} file(s).")
                st.sidebar.json(processed)
            if failed:
                st.sidebar.error(f"Failed {len(failed)} file(s).")
                st.sidebar.json(failed)
            if not processed and not failed:
                st.sidebar.warning("No files were processed.")
        else:
            st.sidebar.error("Failed to upload knowledge files. Please try again.")

if st.sidebar.button("Use Bundled Phone Data"):
    with st.sidebar.status("Updating bundled phone data..."):
        if load_phone_data():
            st.sidebar.success("Bundled phone data updated successfully!")
        else:
            st.sidebar.error("Failed to update bundled phone data. Please try again.")

PROVIDER_CHOICES = ["gemini", "qwen", "openrouter", "ollama", "huggingface"]
PROVIDER_LABELS = {
    "gemini": "Gemini",
    "qwen": "Qwen",
    "openrouter": "OpenRouter",
    "ollama": "Ollama",
    "huggingface": "Hugging Face",
}

if st.session_state.user_id:
    current_selection = st.session_state.get("provider_selection", {})
    current_reasoning = current_selection.get("reasoning_provider", "gemini")
    current_generation = current_selection.get("generation_provider", "gemini")

    def _provider_index(value: str) -> int:
        return PROVIDER_CHOICES.index(value) if value in PROVIDER_CHOICES else 0

    st.sidebar.markdown("**Provider Selection**")
    reasoning_choice = st.sidebar.selectbox(
        "Reasoning",
        PROVIDER_CHOICES,
        index=_provider_index(current_reasoning),
        format_func=lambda v: PROVIDER_LABELS.get(v, v),
        key="reasoning_provider_select",
    )
    generation_choice = st.sidebar.selectbox(
        "Generation",
        PROVIDER_CHOICES,
        index=_provider_index(current_generation),
        format_func=lambda v: PROVIDER_LABELS.get(v, v),
        key="generation_provider_select",
    )

    dirty = (
        reasoning_choice != current_reasoning
        or generation_choice != current_generation
    )
    if st.sidebar.button("적용", disabled=not dirty, key="apply_provider_btn"):
        result = set_provider_selection(
            st.session_state.user_id,
            reasoning_choice,
            generation_choice,
        )
        if result:
            st.session_state.provider_selection = result.get("selection", {})
            st.session_state.embedding_config = result.get("embedding", {})
            st.sidebar.success(
                f"Reasoning={PROVIDER_LABELS[reasoning_choice]} · "
                f"Generation={PROVIDER_LABELS[generation_choice]}"
            )

    def _kv_lines(d: dict) -> str:
        """dict → markdown 키:값 리스트. 중첩 dict 는 한 줄에 inline."""
        lines = []
        for k, v in d.items():
            if isinstance(v, dict):
                inner = " · ".join(f"{ik}=`{iv}`" for ik, iv in v.items())
                lines.append(f"- **{k}**: {inner}" if inner else f"- **{k}**: _(empty)_")
            else:
                lines.append(f"- **{k}**: `{v}`")
        return "\n".join(lines) if lines else "_(none)_"

    if "provider_selection" in st.session_state:
        st.sidebar.caption("Current Providers")
        st.sidebar.markdown(_kv_lines(st.session_state.provider_selection))
        with st.sidebar.expander("Raw JSON", expanded=False):
            st.json(st.session_state.provider_selection)
    if "embedding_config" in st.session_state:
        st.sidebar.caption("Embedding Configuration")
        st.sidebar.markdown(_kv_lines(st.session_state.embedding_config))
        with st.sidebar.expander("Raw JSON", expanded=False):
            st.json(st.session_state.embedding_config)
        st.sidebar.caption("Embedding changes require rebuilding the vector index.")
else:
    st.sidebar.info("Provider controls available after session starts.")

# Check for session timeout
check_session_timeout()

# Chat interface
is_session_active = check_session_active()
if not st.session_state.session_expired and st.session_state.user_id and is_session_active:
    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    # ---------------------------------------------------------------
    # Send box — st.chat_input (bottom-fixed natively) + ingest toggle row.
    # The toggle persists per session via session_state["ingest_flag"].
    # ---------------------------------------------------------------
    if "ingest_flag" not in st.session_state:
        st.session_state["ingest_flag"] = False

    col_left, col_toggle = st.columns([5, 2])
    with col_toggle:
        st.session_state["ingest_flag"] = st.toggle(
            "📚 파일 영구 등록",
            value=st.session_state["ingest_flag"],
            help="ON = 첨부 파일을 벡터스토어에 저장하여 다음 검색에도 사용 / "
                 "OFF = 이 메시지의 컨텍스트로만 사용",
        )

    chat_value = st.chat_input(
        "메시지 입력 — 파일 첨부 가능 (Cmd/Ctrl+Enter 로 전송)",
        accept_file="multiple",
        file_type=["pdf", "docx", "xlsx", "xls", "csv", "txt", "md", "html",
                   "png", "jpg", "jpeg"],
    )

    # st.chat_input with accept_file returns ChatInputValue (or None).
    # Backward-compat: if accept_file is unsupported on this Streamlit
    # version, it returns a plain string instead.
    submitted = False
    prompt_text = ""
    uploaded = []
    if chat_value:
        if isinstance(chat_value, str):
            prompt_text = chat_value
        else:
            prompt_text = (getattr(chat_value, "text", "") or "").strip()
            uploaded = list(getattr(chat_value, "files", []) or [])
        if prompt_text:
            submitted = True
    ingest_flag = st.session_state["ingest_flag"]

    if submitted and prompt_text.strip():
        # Optimistic user message
        st.session_state.messages.append({"role": "user", "content": prompt_text.strip()})
        update_session_activity()
        with st.chat_message("user"):
            st.write(prompt_text.strip())
            if uploaded:
                for f in uploaded:
                    st.caption(f"📎 {f.name} ({f.size} bytes)")

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response_data = msgs_api.send_message(
                    text=prompt_text.strip(),
                    conversation_id=st.session_state.get("active_conversation_id"),
                    files=uploaded or [],
                    ingest=ingest_flag,
                    top_k=st.session_state.get("knob_top_k", 5),
                    use_reasoning=st.session_state.get("knob_use_reasoning", False),
                    history_turns=st.session_state.get("knob_history_turns", 5),
                )

                if response_data and response_data.get("blocked"):
                    blocked_words = response_data.get("blocked_words", [])
                    categories = response_data.get("categories", [])
                    next_steps = response_data.get("next_steps", [])
                    words_chip = " · ".join(f"`{w}`" for w in blocked_words) or "—"
                    cat_chip = " · ".join(categories) or "—"
                    block_html = f"""
<div style="border:1px solid #D9A441;background:rgba(217,164,65,0.08);
            border-radius:6px;padding:12px 16px;margin:8px 0;
            font-family:-apple-system,'Pretendard Variable',sans-serif;">
  <div style="font-weight:500;color:#D9A441;font-family:'Geist Mono',monospace;
              font-size:11px;letter-spacing:0.09em;text-transform:uppercase;">
    BLOCKED · MODERATION
  </div>
  <div style="margin-top:6px;color:#F3F2EE;">
    질문에 차단된 표현이 포함되어 답변이 중단되었습니다.
  </div>
  <div style="margin-top:8px;color:#8B8B93;font-family:'Geist Mono',monospace;
              font-size:12px;">
    Words: {words_chip} &nbsp;·&nbsp; Categories: {cat_chip}
  </div>
</div>"""
                    st.markdown(block_html, unsafe_allow_html=True)
                    if next_steps:
                        st.markdown("**다음 단계**")
                        st.markdown("\n".join(f"- {s}" for s in next_steps))
                    st.session_state.messages.append(
                        {"role": "assistant", "content": "[BLOCKED — moderation]"}
                    )
                elif response_data:
                    asst = response_data.get("assistant_message", {}) or {}
                    response_text = asst.get("content", "Sorry, I couldn't process that.")
                    redacted_count = asst.get("redacted_count", 0)
                    st.write(response_text)
                    if redacted_count > 0:
                        st.warning(
                            f"[수정됨·{redacted_count}건] 권한 외 chunk 가 검색결과에서 가려졌습니다. "
                            "접근 권한 확장은 관리자에게 문의하세요."
                        )
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": response_text,
                        "redacted_count": redacted_count,
                    })
                    # New conv created? Persist active id and refresh sidebar.
                    new_conv_id = response_data.get("conversation_id")
                    if new_conv_id and st.session_state.get("active_conversation_id") != new_conv_id:
                        st.session_state["active_conversation_id"] = new_conv_id
                else:
                    st.error("응답을 받지 못했습니다. 다시 시도해 주세요.")
        st.rerun()

else:
    st.warning("Your session has expired. Please refresh the page to start a new session.")
    if st.button("Start New Session", key="main_new_session"):
        st.session_state.session_expired = False
        st.session_state.messages = []
        st.rerun()

# New session button in sidebar (forces re-login)
if st.sidebar.button("Start New Session"):
    auth_mod.logout()
    st.rerun()
