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

# Ensure Redis container exists and can be reached
check_redis() {
    echo "Ensuring Redis container is running..."

    if ! docker ps -a --format '{{.Names}}' | grep -wq '^redis$'; then
        echo "Redis container not found. Creating redis:7 container..."
        docker run -d -p 6379:6379 --name redis redis:7 >/dev/null
        sleep 3
    elif ! docker ps --format '{{.Names}}' | grep -wq '^redis$'; then
        echo "Starting existing Redis container..."
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

# Load environment variables from backend .env using POSIX-safe approach
if [ -f "$BACKEND_DIR/.env" ]; then
    echo "Loading environment variables from backend/.env file..."
    set -a
    # shellcheck disable=SC1090
    source "$BACKEND_DIR/.env"
    set +a
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

echo "Starting Celery worker..."
(
    cd "$BACKEND_DIR"
    PYTHONUNBUFFERED=1 "$BACKEND_PYTHON" -m celery -A triple_chat_pjt worker --loglevel=info
) &
worker_pid=$!

sleep 2
if ! kill -0 "$worker_pid" 2>/dev/null; then
    echo "Celery worker failed to start"
else
    echo "Celery worker PID: $worker_pid"
fi

echo "Starting Celery beat..."
(
    cd "$BACKEND_DIR"
    PYTHONUNBUFFERED=1 "$BACKEND_PYTHON" -m celery -A triple_chat_pjt beat --loglevel=info
) &
beat_pid=$!

sleep 2
if ! kill -0 "$beat_pid" 2>/dev/null; then
    echo "Celery beat failed to start"
else
    echo "Celery beat PID: $beat_pid"
fi

echo "==== All services started successfully! ===="
echo "Django backend PID: $backend_pid (http://localhost:8000)"
echo "Streamlit frontend PID: $frontend_pid (http://localhost:8501)"
echo "Celery worker PID: $worker_pid"
echo "Celery beat PID: $beat_pid"
echo ""
echo "Press Ctrl+C to stop all services"

cleanup() {
    echo "Cleaning up processes..."
    [ -n "$backend_pid" ] && kill "$backend_pid" 2>/dev/null
    [ -n "$frontend_pid" ] && kill "$frontend_pid" 2>/dev/null
    [ -n "$worker_pid" ] && kill "$worker_pid" 2>/dev/null
    [ -n "$beat_pid" ] && kill "$beat_pid" 2>/dev/null
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

wait_for_exit "$backend_pid" "$frontend_pid" "$worker_pid" "$beat_pid"

cleanup
