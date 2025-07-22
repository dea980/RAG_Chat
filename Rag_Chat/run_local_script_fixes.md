# Run Local Script Analysis and Fixes

## Issues Found in Original Script

I've analyzed `run_local.sh` and identified several potential issues that could cause errors:

### 0. Runtime Errors Found
When running the script, the following errors were encountered:
- `Module 'triple_chat_pjt' has no attribute 'celery'` - The Celery configuration was missing/incorrect
- `NameError: name 'os' is not defined` in frontend/app.py - Missing import

### 1. Virtual Environment Issues
- The original script tries to activate a virtual environment at `venv/bin/activate` in the root directory
- There are separate virtual environments in the backend, frontend, and root directories
- This could lead to missing dependencies depending on which environment was properly set up

### 2. Database Path Issues
- The `.env` file specifies `DATABASE_URL=sqlite:///db/db.sqlite3`
- The script sets `DATABASE_URL=sqlite:///backend/db/db.sqlite3`
- Neither path is correct, as database files exist directly in the root and backend directories
- No `db` directory was found in the backend folder

### 3. Requirements Issues
- The `backend/requirements.txt` file has unresolved Git merge conflicts:
```
<<<<<<< Updated upstream
=======
openai>=1.0.0
chromadb==0.4.22
pandas>=2.1.4
openpyxl>=3.1.2
>>>>>>> Stashed changes
```
- This will cause pip installation to fail

### 4. Docker Dependency
- The script requires Docker to be running for Redis
- No check is done to verify Docker is running before attempting to use it

### 5. Environment Variable Handling
- Script sets variables that overlap with those in `.env`
- OpenAI API key might not be properly exported or checked

### 6. Process Management Issues
- Port conflict resolution may fail due to permissions
- PIDs are tracked but no cleanup mechanism if script is interrupted

## Improvements in Fixed Script

The `run_local_fixed.sh` script includes the following improvements:

### 1. Virtual Environment Handling
- Checks for virtual environments in multiple locations (root, backend, frontend)
- Uses the first one found, or creates a new one if none exist
- Properly activates the frontend's virtual environment when running Streamlit

### 2. Database Path Management
- Ensures the database directory exists or creates it
- Uses consistent path references with absolute paths
- Sets DATABASE_URL only if not already set from .env

### 3. Requirements Fixing
- Automatically detects and fixes merge conflicts in requirements files
- Uses sed to remove conflict markers before installation

### 4. Docker and Redis Checks
- Verifies Docker is running before attempting to use it
- Retries Redis connection after starting the container
- Provides clear error messages if Redis fails to connect

### 5. Better Environment Variable Handling
- Loads variables from .env file first
- Only sets default values if not already set from .env
- Checks for critical variables like OPENAI_API_KEY

### 6. Process Management
- Adds a cleanup function to properly terminate all processes
- Sets a trap to catch interrupts (Ctrl+C)
- Provides clear status reporting for all services

### 7. Virtual Environment Improvements
- Uses the specific Python from activated virtual environments with `$(which python)`
- Ensures Python modules are executed from the correct environment context
- Explicitly installs required dependencies for both frontend and backend
- Better virtual environment activation management across directories

### 8. Additional Improvements
- Added more error checking and validation
- Better directory structure management
- More informative output messages
- Cleanup on script interruption

## Additional Code Fixes Made

In addition to fixing the script, we also fixed several issues in the application code:

### 1. Frontend App Fixes (frontend/app.py)
- Added missing imports: `import os` and `import time`
- Fixed duplicate `listen_to_redis()` function (merged functionality)
- Fixed variable order: Moved `INACTIVITY_CHECK_INTERVAL` definition before its usage
- Created needed functions: `check_session_timeout()`, `load_phone_data()`
- Added a simple Redis manager class to handle Redis connections
- Fixed `redis_manager` definition order (moved it before first usage)
- Fixed typo in application title
- Properly defined `is_session_active` variable

### 2. Celery Configuration Fixes
- Created a proper `celery.py` file with the necessary configuration
```python
import os
from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'triple_chat_pjt.settings')

# Create the Celery app
app = Celery('triple_chat_pjt')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
```

- Updated `__init__.py` to import the Celery app
```python
# This will make sure the app is always imported when
# Django starts so that shared_task will use this app.
from .celery import app as celery_app

__all__ = ('celery_app',)
```

## How to Use

1. Make the script executable: `chmod +x run_local_fixed.sh`
2. Run the script: `./run_local_fixed.sh`
3. Press Ctrl+C to gracefully stop all services when done

The script will automatically:
- Start Redis in Docker
- Fix any merge conflicts in requirements files
- Set up proper virtual environments
- Start Django backend, Streamlit frontend, and Celery worker/beat
- Provide URLs and PIDs for all running services