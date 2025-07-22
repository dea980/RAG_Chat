#!/bin/bash

# Function to check and kill process using a specific port
kill_port_process() {
    local port=$1
    local process_name=$2
    if lsof -i :$port > /dev/null; then
        echo "Port $port is in use. Killing existing $process_name process..."
        lsof -ti :$port | xargs kill -9
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

# Function to check Redis connection
check_redis() {
    echo "Testing Redis connection..."
    if ! docker exec redis redis-cli ping > /dev/null; then
        echo "Failed to connect to Redis. Starting Redis container..."
        docker start redis || docker run -d -p 6379:6379 --name redis redis:7
        sleep 3
        
        # Test connection again
        if ! docker exec redis redis-cli ping > /dev/null; then
            echo "Failed to connect to Redis after restart"
            return 1
        fi
    fi
    echo "Redis connection successful"
    return 0
}

# Function to fix backend requirements
fix_requirements() {
    # Check if there are merge conflicts in the requirements file
    if grep -q "<<<<<<< " backend/requirements.txt; then
        echo "Detected merge conflicts in backend/requirements.txt. Creating fixed version..."
        # Create a fixed version without the conflict markers
        sed '/^<<<<<<< /d; /^=======$/d; /^>>>>>>> /d' backend/requirements.txt > backend/requirements_fixed.txt
        mv backend/requirements_fixed.txt backend/requirements.txt
        echo "Fixed backend/requirements.txt"
    fi
}

# Start setup
echo "==== Starting project setup ===="

# Check Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "Docker is not running. Please start Docker and try again."
    exit 1
fi

# Start Redis
echo "Starting Redis..."
check_redis
if [ $? -ne 0 ]; then
    echo "Failed to start Redis. Exiting."
    exit 1
fi

# Fix backend requirements file if needed
fix_requirements

# Ensure database directory exists
ensure_directory "backend/db"

# Activate the correct virtual environment
if [ -d "venv/bin" ]; then
    echo "Activating root virtual environment..."
    source venv/bin/activate
elif [ -d "backend/venv/bin" ]; then
    echo "Activating backend virtual environment..."
    source backend/venv/bin/activate
else
    echo "No virtual environment found. Creating one in the root directory..."
    python -m venv venv
    source venv/bin/activate
    
    # Install requirements
    echo "Installing project requirements..."
    pip install -r requirements.txt
    echo "Installing essential dependencies..."
    pip install watchdog celery redis
fi

# Load environment variables from .env file
if [ -f backend/.env ]; then
    echo "Loading environment variables from backend/.env file..."
    export $(cat backend/.env | grep -v '^#' | xargs)
fi

# Set environment variables if not already set
export DEBUG=${DEBUG:-1}
export DATABASE_URL=${DATABASE_URL:-"sqlite:///$(pwd)/backend/db/db.sqlite3"}
export REDIS_HOST=${REDIS_HOST:-"localhost"}
export REDIS_PORT=${REDIS_PORT:-6379}
export REDIS_URL=${REDIS_URL:-"redis://localhost:6379/0"}
export BACKEND_URL=${BACKEND_URL:-"http://localhost:8000"}

# Verify OpenAI API key is available
if [ -z "$OPENAI_API_KEY" ]; then
    echo "Warning: OPENAI_API_KEY is not set. Some functionality may not work."
fi

# Kill any process using Django port (8000)
kill_port_process 8000 "Django"

# Django backend setup
echo "Setting up Django backend..."
cd backend

# Make database directory if it doesn't exist
ensure_directory "db"

echo "Making migrations..."
$(which python) manage.py makemigrations

echo "Applying migrations..."
$(which python) manage.py migrate

echo "Starting Django backend..."
PYTHONUNBUFFERED=1 $(which python) manage.py runserver 0.0.0.0:8000 &
backend_pid=$!
cd ..

echo "Waiting for Django to start..."
sleep 5

# Check if Django server is running
if ! kill -0 $backend_pid 2>/dev/null; then
    echo "Django server failed to start"
    exit 1
fi

# Kill any process using Streamlit port (8501)
kill_port_process 8501 "Streamlit"

# Streamlit frontend setup
echo "Starting Streamlit frontend..."
cd frontend

# Setup frontend environment if needed
if [ ! -d "venv/bin" ] && [ ! -f "venv/bin/activate" ]; then
    echo "Setting up frontend virtual environment..."
    python -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# Install any missing dependencies
pip install -r requirements.txt

# Start Streamlit - use the Python from the virtual environment explicitly
PYTHONUNBUFFERED=1 \
REDIS_URL="redis://localhost:6379/0" \
REDIS_HOST="localhost" \
REDIS_PORT=6379 \
BACKEND_URL="http://localhost:8000" \
OPENAI_API_KEY="$OPENAI_API_KEY" \
$(which python) -m streamlit run app.py &
frontend_pid=$!
cd ..

sleep 2

# Check if Streamlit is running
if ! kill -0 $frontend_pid 2>/dev/null; then
    echo "Streamlit failed to start"
    echo "Cleaning up Django process..."
    kill $backend_pid
    exit 1
fi

# Go back to backend for Celery
cd backend

# Start Celery worker
echo "Starting Celery worker..."
PYTHONUNBUFFERED=1 $(which python) -m celery -A triple_chat_pjt worker --loglevel=info &
worker_pid=$!

if ! kill -0 $worker_pid 2>/dev/null; then
    echo "Celery worker failed to start"
else
    echo "Celery worker PID: $worker_pid"
fi

# Start Celery beat
echo "Starting Celery beat..."
PYTHONUNBUFFERED=1 $(which python) -m celery -A triple_chat_pjt beat --loglevel=info &
beat_pid=$!

if ! kill -0 $beat_pid 2>/dev/null; then
    echo "Celery beat failed to start"
else
    echo "Celery beat PID: $beat_pid"
fi

cd ..

echo "==== All services started successfully! ===="
echo "Django backend PID: $backend_pid (http://localhost:8000)"
echo "Streamlit frontend PID: $frontend_pid (http://localhost:8501)"
echo "Celery worker PID: $worker_pid"
echo "Celery beat PID: $beat_pid"
echo ""
echo "Press Ctrl+C to stop all services"

# Create a cleanup function
cleanup() {
    echo "Cleaning up processes..."
    kill $backend_pid $frontend_pid $worker_pid $beat_pid 2>/dev/null
    exit 0
}

# Set trap to catch SIGINT
trap cleanup SIGINT

# Wait for any process to exit
wait -n

# Exit with status of process that exited first
exit $?