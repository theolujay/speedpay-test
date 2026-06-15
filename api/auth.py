"""JWT authentication helpers and token utilities."""

from typing import Optional

import jwt
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from ninja.security import HttpBearer
from ninja.errors import HttpError

from api.models import User


class JWTAuth(HttpBearer):
    """Authenticates requests via JWT bearer token."""

    def authenticate(self, request, token: str) -> Optional[User]:
        if not token:
            return None
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            user_id = payload.get("user_id")
            if not user_id:
                return None
            user = User.objects.get(id=user_id)
            return user
        except jwt.ExpiredSignatureError:
            raise HttpError(401, "Token has expired")
        except jwt.InvalidTokenError:
            raise HttpError(401, "Invalid token")
        except User.DoesNotExist:
            return None


class AdminAuth(HttpBearer):
    """Authenticates requests and enforces admin role."""

    def authenticate(self, request, token: str) -> Optional[User]:
        if not token:
            return None
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            user_id = payload.get("user_id")
            if not user_id:
                return None
            user = User.objects.get(id=user_id)
            if not user.is_admin:
                raise HttpError(403, "Admin access required")
            return user
        except jwt.ExpiredSignatureError:
            raise HttpError(401, "Token has expired")
        except jwt.InvalidTokenError:
            raise HttpError(401, "Invalid token")
        except User.DoesNotExist:
            return None


def create_access_token(user: User) -> str:
    """Create a short-lived JWT access token."""
    payload = {
        "user_id": str(user.id),
        "email": user.email,
        "exp": timezone.now() + timedelta(hours=1),
        "iat": timezone.now(),
        "type": "access",
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def create_refresh_token(user: User) -> str:
    """Create a long-lived JWT refresh token."""
    payload = {
        "user_id": str(user.id),
        "exp": timezone.now() + timedelta(days=7),
        "iat": timezone.now(),
        "type": "refresh",
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def create_tokens_for_user(user: User) -> dict:
    """Return both access and refresh tokens for a user."""
    return {"access": create_access_token(user), "refresh": create_refresh_token(user)}


def refresh_access_token(refresh_token: str) -> Optional[str]:
    """Issue a new access token from a valid refresh token."""
    try:
        payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=["HS256"])
        if payload.get("type") != "refresh":
            return None
        user_id = payload.get("user_id")
        user = User.objects.get(id=user_id)
        return create_access_token(user)
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, User.DoesNotExist):
        return None
