#!/usr/bin/env bash

# Determine which Python interpreter to use for creating virtual environments
PYTHON_BIN=${PYTHON_BIN:-python3}
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    PYTHON_BIN=python
fi

ROOT_DIR=$(pwd)
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
BACKEND_VENV="$BACKEND_DIR/venv"
FRONTEND_VENV="$FRONTEND_DIR/venv"
BACKEND_PYTHON="$BACKEND_VENV/bin/python"
FRONTEND_PYTHON="$FRONTEND_VENV/bin/python"

# Function to check and kill process using a specific port
kill_port_process() {
    local port=$1
    local process_name=$2
    if lsof -i :"$port" >/dev/null 2>&1; then
        echo "Port $port is in use. Killing existing $process_name process..."
        lsof -ti :"$port" | xargs kill -9
        sleep 2
    fi
}

# Function to check if directory exists, if not create it
ensure_directory() {
    if [ ! -d "$1" ]; then
        echo "Creating directory: $1"
        mkdir -p "$1"
    fi
}

# Ensure Postgres container exists and can be reached (opt-in via USE_POSTGRES=1).
# Reuses an existing container on the target port (e.g. docker-compose's
# rag_chat-postgres-1) before creating a fresh sh-managed one.
check_postgres() {
    local pg_db=${POSTGRES_DB:-triple_chat}
    local pg_user=${POSTGRES_USER:-postgres}
    local pg_password=${POSTGRES_PASSWORD:-postgres}
    local pg_host_port=${POSTGRES_HOST_PORT:-5434}

    echo "Ensuring Postgres is running on localhost:${pg_host_port}..."

    # 1) Reuse: any container already publishing the target host port
    local existing
    existing=$(docker ps --format '{{.Names}} {{.Ports}}' \
        | awk -v p=":${pg_host_port}->" '$0 ~ p {print $1; exit}')
    if [ -n "$existing" ]; then
        echo "Reusing running Postgres container '${existing}' on port ${pg_host_port}."
        export DATABASE_URL="postgres://${pg_user}:${pg_password}@localhost:${pg_host_port}/${pg_db}"
        return 0
    fi

    # 2) Otherwise manage a dedicated container
    if ! docker ps -a --format '{{.Names}}' | grep -wq '^triple_chat_postgres$'; then
        echo "Creating postgres:16-alpine container 'triple_chat_postgres'..."
        docker run -d \
            -p "${pg_host_port}:5432" \
            -e POSTGRES_DB="$pg_db" \
            -e POSTGRES_USER="$pg_user" \
            -e POSTGRES_PASSWORD="$pg_password" \
            -v triple_chat_postgres_data:/var/lib/postgresql/data \
            --name triple_chat_postgres \
            postgres:16-alpine >/dev/null
        sleep 5
    elif ! docker ps --format '{{.Names}}' | grep -wq '^triple_chat_postgres$'; then
        echo "Starting existing 'triple_chat_postgres' container..."
        docker start triple_chat_postgres >/dev/null
        sleep 3
    fi

    local retries=10
    while ! docker exec triple_chat_postgres pg_isready -U "$pg_user" -d "$pg_db" >/dev/null 2>&1; do
        retries=$((retries - 1))
        if [ "$retries" -le 0 ]; then
            echo "Failed to reach Postgres container 'triple_chat_postgres'."
            return 1
        fi
        sleep 1
    done

    echo "Postgres container is running on localhost:${pg_host_port}."
    export DATABASE_URL="postgres://${pg_user}:${pg_password}@localhost:${pg_host_port}/${pg_db}"
    return 0
}

# Ensure Redis container exists and can be reached.
# Reuses any running container publishing port 6379 (e.g. docker-compose's
# rag_chat-redis-1) before creating a fresh sh-managed one.
check_redis() {
    local redis_host_port=${REDIS_HOST_PORT:-6379}
    echo "Ensuring Redis is running on localhost:${redis_host_port}..."

    # 1) Reuse: any container already publishing the target port
    local existing
    existing=$(docker ps --format '{{.Names}} {{.Ports}}' \
        | awk -v p=":${redis_host_port}->" '$0 ~ p {print $1; exit}')
    if [ -n "$existing" ]; then
        if docker exec "$existing" redis-cli ping >/dev/null 2>&1; then
            echo "Reusing running Redis container '${existing}'."
            return 0
        fi
        echo "Container '${existing}' is on port ${redis_host_port} but not responding to PING."
        return 1
    fi

    # 2) Otherwise manage a dedicated container
    if ! docker ps -a --format '{{.Names}}' | grep -wq '^redis$'; then
        echo "Creating redis:7 container 'redis'..."
        docker run -d -p "${redis_host_port}:6379" --name redis redis:7 >/dev/null
        sleep 3
    elif ! docker ps --format '{{.Names}}' | grep -wq '^redis$'; then
        echo "Starting existing 'redis' container..."
        docker start redis >/dev/null
        sleep 3
    fi

    if ! docker exec redis redis-cli ping >/dev/null 2>&1; then
        echo "Failed to connect to Redis container 'redis'."
        return 1
    fi

    echo "Redis container is running."
    return 0
}

# Function to fix backend requirements merge conflicts if needed
fix_requirements() {
    if [ -f "$BACKEND_DIR/requirements.txt" ] && grep -q "<<<<<<< " "$BACKEND_DIR/requirements.txt"; then
        echo "Detected merge conflicts in backend/requirements.txt. Creating fixed version..."
        sed '/^<<<<<<< /d; /^=======$/d; /^>>>>>>> /d' "$BACKEND_DIR/requirements.txt" > "$BACKEND_DIR/requirements_fixed.txt"
        mv "$BACKEND_DIR/requirements_fixed.txt" "$BACKEND_DIR/requirements.txt"
        echo "Fixed backend/requirements.txt"
    fi
}

# Ensure backend virtual environment and dependencies are ready
setup_backend_env() {
    if [ ! -d "$BACKEND_VENV/bin" ]; then
        echo "Creating backend virtual environment..."
        "$PYTHON_BIN" -m venv "$BACKEND_VENV"
    fi

    echo "Installing backend dependencies..."
    "$BACKEND_PYTHON" -m pip install --upgrade pip
    if [ -f "$BACKEND_DIR/requirements.txt" ]; then
        "$BACKEND_PYTHON" -m pip install -r "$BACKEND_DIR/requirements.txt"
    else
        echo "Warning: backend/requirements.txt not found; skipping dependency install."
    fi
}

# Ensure frontend virtual environment and dependencies are ready
setup_frontend_env() {
    if [ ! -d "$FRONTEND_VENV/bin" ]; then
        echo "Creating frontend virtual environment..."
        "$PYTHON_BIN" -m venv "$FRONTEND_VENV"
    fi

    echo "Installing frontend dependencies..."
    "$FRONTEND_PYTHON" -m pip install --upgrade pip
    if [ -f "$FRONTEND_DIR/requirements.txt" ]; then
        "$FRONTEND_PYTHON" -m pip install -r "$FRONTEND_DIR/requirements.txt"
    else
        echo "Warning: frontend/requirements.txt not found; skipping dependency install."
    fi
}

echo "==== Starting project setup ===="

# Check Docker is running
if ! docker info >/dev/null 2>&1; then
    echo "Docker is not running. Please start Docker and try again."
    exit 1
fi

# Ensure Redis container is healthy
if ! check_redis; then
    echo "Failed to start or connect to Redis. Exiting."
    exit 1
fi

# Fix backend requirements if there are unresolved conflicts
fix_requirements

# Ensure backend database directory exists
ensure_directory "$BACKEND_DIR/db"
ensure_directory "$BACKEND_DIR/static"

# Prepare backend environment
setup_backend_env

# Load environment variables from the single root .env (source of truth).
# backend/.env was consolidated into Rag_Chat/.env — see backend/README.md
# "Environment variables" section for the inline template.
if [ -f "$ROOT_DIR/.env" ]; then
    echo "Loading environment variables from .env file..."
    set -a
    # shellcheck disable=SC1090
    source "$ROOT_DIR/.env"
    set +a
fi

# Optional Postgres container (USE_POSTGRES=1 for prod parity, default = SQLite).
# Runs after .env load so POSTGRES_* and USE_POSTGRES can come from .env.
if [ "${USE_POSTGRES:-0}" = "1" ]; then
    if ! check_postgres; then
        echo "Failed to start or connect to Postgres. Exiting."
        exit 1
    fi
fi

# Set environment variables if not already set
export DEBUG=${DEBUG:-1}
export DATABASE_URL=${DATABASE_URL:-"sqlite:///$BACKEND_DIR/db/db.sqlite3"}
export REDIS_HOST=${REDIS_HOST:-"localhost"}
export REDIS_PORT=${REDIS_PORT:-6379}
export REDIS_URL=${REDIS_URL:-"redis://localhost:6379/0"}
export BACKEND_URL=${BACKEND_URL:-"http://localhost:8000"}

if [ -z "$GOOGLE_API_KEY" ]; then
    echo "Warning: GOOGLE_API_KEY is not set. Some functionality may not work."
fi

if [ -n "$QWEN_API_KEY" ]; then
    export QWEN_API_KEY
fi
if [ -n "$QWEN_API_BASE" ]; then
    export QWEN_API_BASE
fi
if [ -n "$QWEN_MODEL_NAME" ]; then
    export QWEN_MODEL_NAME
fi

# Kill any process using Django port (8000)
kill_port_process 8000 "Django"

echo "Setting up Django backend..."

echo "Making migrations..."
(cd "$BACKEND_DIR" && "$BACKEND_PYTHON" manage.py makemigrations )

echo "Applying migrations..."
(cd "$BACKEND_DIR" && "$BACKEND_PYTHON" manage.py migrate )

echo "Starting Django backend..."
(
    cd "$BACKEND_DIR"
    PYTHONUNBUFFERED=1 "$BACKEND_PYTHON" manage.py runserver 0.0.0.0:8000
) &
backend_pid=$!

echo "Waiting for Django to start..."
sleep 5

if ! kill -0 "$backend_pid" 2>/dev/null; then
    echo "Django server failed to start"
    exit 1
fi

# Prepare frontend environment
setup_frontend_env

# Kill any process using Streamlit port (8501)
kill_port_process 8501 "Streamlit"

echo "Starting Streamlit frontend..."
(
    cd "$FRONTEND_DIR"
    PYTHONUNBUFFERED=1 \
    REDIS_URL="$REDIS_URL" \
    REDIS_HOST="$REDIS_HOST" \
    REDIS_PORT="$REDIS_PORT" \
    BACKEND_URL="$BACKEND_URL" \
    GOOGLE_API_KEY="$GOOGLE_API_KEY" \
    QWEN_API_KEY="$QWEN_API_KEY" \
    QWEN_API_BASE="$QWEN_API_BASE" \
    QWEN_MODEL_NAME="$QWEN_MODEL_NAME" \
    "$FRONTEND_PYTHON" -m streamlit run app.py
) &
frontend_pid=$!

sleep 5

if ! kill -0 "$frontend_pid" 2>/dev/null; then
    echo "Streamlit failed to start"
    echo "Cleaning up Django process..."
    kill "$backend_pid"
    exit 1
fi

echo "==== All services started successfully! ===="
echo "Django backend PID: $backend_pid (http://localhost:8000)"
echo "Streamlit frontend PID: $frontend_pid (http://localhost:8501)"
echo ""
echo "Press Ctrl+C to stop all services"

cleanup() {
    echo "Cleaning up processes..."
    [ -n "$backend_pid" ] && kill "$backend_pid" 2>/dev/null
    [ -n "$frontend_pid" ] && kill "$frontend_pid" 2>/dev/null
    exit 0
}

trap cleanup SIGINT SIGTERM

wait_for_exit() {
    local pids=("$@")
    while true; do
        for pid in "${pids[@]}"; do
            if [ -n "$pid" ] && ! kill -0 "$pid" 2>/dev/null; then
                return 0
            fi
        done
        sleep 1
    done
}

wait_for_exit "$backend_pid" "$frontend_pid"

cleanup
