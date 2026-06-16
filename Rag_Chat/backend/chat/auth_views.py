"""B3 — Session-based login/logout API.

Endpoints:
- POST /api/v1/triple/auth/login/   {email, password}  → 200 + user info + session cookie
- POST /api/v1/triple/auth/logout/                     → 204 (flushes session)
- GET  /api/v1/triple/auth/me/                         → 200 (current user) or 401

`authenticate()` uses `ModelBackend` (default) which calls
`User.check_password()` against the pbkdf2 hash from B1. `login()` sets the
session cookie that subsequent requests carry — `request.user` is populated
by `AuthenticationMiddleware` for any view downstream.
"""
from __future__ import annotations

from django.contrib.auth import authenticate, login, logout
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


def _user_payload(user) -> dict:
    return {
        "user_id": user.user_id,
        "email": user.email,
        "role": user.role,
        "access_level": user.access_level,
        "is_staff": user.is_staff,
    }


class LoginAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")
        if not email or not password:
            return Response(
                {"error": "email and password required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # `authenticate` returns None for wrong password OR inactive user.
        user = authenticate(request, username=email, password=password)
        if user is None:
            return Response(
                {"error": "invalid credentials"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        login(request, user)
        return Response(_user_payload(user), status=status.HTTP_200_OK)


class LogoutAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(_user_payload(request.user))
