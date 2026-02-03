"""Session/token helpers for demo and production scenarios.

This module exposes two simple strategies so we can toggle behaviour while
keeping the calling code identical:

1. `issue_demo_token` / `validate_demo_token`
    - Returns the Django ``User.user_id`` directly.
    - Useful for local prototypes where we only need a stable identifier.

2. `issue_jwt_token` / `validate_jwt_token`
    - Generates a signed JWT using the project secret key.
    - Suited for production: tokens carry an expiry and can be validated without hitting the database on every request.

Switching strategies lets us keep API tests fast while having a clear upgrade
path for the React client.
"""

from __future__ import annotations

import datetime
import os
import sys
from pathlib import Path
from typing import Optional, TYPE_CHECKING

import django
from django.conf import settings
from django.utils import timezone
from jose import JWTError, jwt
from django.apps import apps


# Ensure Django knows how to locate settings when executed as a script.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "triple_chat_pjt.settings")

# When executed directly (`python backend/chat/session_strategies.py`) the
# relative imports below would fail unless we add the project root to PYTHONPATH.
if __package__ in (None, ""):
    ROOT_DIR = Path(__file__).resolve().parents[2]
    if str(ROOT_DIR) not in sys.path:
        sys.path.append(str(ROOT_DIR))
    django.setup()

if TYPE_CHECKING:
    from .models import User  # pragma: no cover
elif __package__ in (None, ""):
    from backend.chat.models import User
else:
    from .models import User


# Demo strategy ------------------------------------------------------------

def issue_demo_token(user: User) -> str:
    """Return the user's ID directly for quick local testing."""
    return user.user_id


def validate_demo_token(token: str) -> Optional[User]:
    """Resolve the plain user_id token back to a user instance."""

    if not token:
        return None

    try:
        return User.objects.get(user_id=token)
    except User.DoesNotExist:
        return None


# JWT strategy -------------------------------------------------------------

JWT_ALGORITHM = "HS256"
DEFAULT_JWT_EXP_MINUTES = 60


def _jwt_secret() -> str:
    secret = getattr(settings, "SESSION_JWT_SECRET", None) or settings.SECRET_KEY
    if not secret:
        raise RuntimeError("SESSION_JWT_SECRET or SECRET_KEY must be configured")
    return secret


def issue_jwt_token(user: User, *, expires_minutes: int = DEFAULT_JWT_EXP_MINUTES) -> str:
    """Create a signed JWT embedding the user ID and expiry."""

    expiry = timezone.now() + datetime.timedelta(minutes=expires_minutes)
    payload = {
        "sub": user.user_id,
        "exp": expiry,
        "iat": timezone.now(),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGORITHM)


def validate_jwt_token(token: str) -> Optional[User]:
    """Verify the token signature and fetch the related user."""

    if not token:
        return None

    try:
        payload = jwt.decode(token, _jwt_secret(), algorithms=[JWT_ALGORITHM])
    except JWTError:
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    try:
        return User.objects.get(user_id=user_id)
    except User.DoesNotExist:
        return None


# Local toggle -------------------------------------------------------------

def get_session_functions(use_jwt: bool = False):
    """Utility to pick the strategy at runtime (useful for tests/CLI)."""

    if use_jwt:
        return issue_jwt_token, validate_jwt_token
    return issue_demo_token, validate_demo_token


if __name__ == "__main__":  # Simple local smoke test
    # Run with: `python -m backend.chat.session_strategies`
    if not apps.ready:
        django.setup()

    demo_issue, demo_validate = get_session_functions()
    jwt_issue, jwt_validate = get_session_functions(use_jwt=True)

    # Using the latest user record for demonstration purposes.
    try:
        sample_user = User.objects.order_by("-created_datetime").first()
    except Exception as exc:  # pragma: no cover - defensive guard
        raise SystemExit(f"Failed to load user for test: {exc}")

    if not sample_user:
        raise SystemExit("No users found. Create a user before running this script.")

    print("== Demo token strategy ==")
    token = demo_issue(sample_user)
    print("issued:", token)
    print("validated:", demo_validate(token))

    print("\n== JWT token strategy ==")
    jwt_token = jwt_issue(sample_user)
    print("issued:", jwt_token)
    print("validated:", jwt_validate(jwt_token))
