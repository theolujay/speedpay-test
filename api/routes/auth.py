import logging
from django.db import DatabaseError, transaction
from ninja import Router
from ninja.responses import Response

from api.auth import create_tokens_for_user, refresh_access_token
from api.models import User, Account, generate_account_number
from api.schemas import (
    RegisterRequest,
    RegisterResponse,
    TokenRequest,
    TokenResponse,
    RefreshTokenRequest,
)
from api.exceptions import InvalidRequestException

logger = logging.getLogger(__name__)

router = Router()


@router.post(
    "/register",
    response=RegisterResponse,
    url_name="auth-register",
    auth=None,
    summary="Register a new user",
)
def register(request, payload: RegisterRequest):
    """Create a new user and account with a unique 6-digit account number."""
    if User.objects.filter(email=payload.email).exists():
        raise InvalidRequestException("A user with this email already exists")

    try:
        with transaction.atomic():
            user = User.objects.create_user(
                email=payload.email,
                password=payload.password,
                first_name=payload.first_name,
                last_name=payload.last_name,
            )
            account = Account.objects.create(
                user=user,
                number=generate_account_number(),
            )
    except DatabaseError as e:
        logger.error(f"Database error during registration: {e}")
        return Response({"detail": "Registration failed"}, status=503)

    logger.info(f"User registered: {user.email}, account: {account.number}")
    return {
        "id": str(user.id),
        "email": user.email,
        "number": account.number,
    }


@router.post(
    "/token",
    response=TokenResponse,
    url_name="auth-token",
    auth=None,
    summary="Obtain JWT tokens",
)
def token(request, payload: TokenRequest):
    """Exchange email and password for access and refresh JWT tokens."""
    try:
        user = User.objects.get(email=payload.email)
    except User.DoesNotExist:
        raise InvalidRequestException("Invalid email or password")

    if not user.check_password(payload.password):
        raise InvalidRequestException("Invalid email or password")

    if not user.is_active:
        raise InvalidRequestException("Account is inactive")

    tokens = create_tokens_for_user(user)
    logger.info(f"Token issued for: {user.email}")
    return tokens


@router.post(
    "/token/refresh",
    response=dict,
    url_name="auth-token-refresh",
    auth=None,
    summary="Refresh access token",
)
def refresh_token(request, payload: RefreshTokenRequest):
    """Exchange a refresh token for a new access token."""
    new_access = refresh_access_token(payload.refresh)
    if not new_access:
        raise InvalidRequestException("Invalid or expired refresh token")
    return {"access": new_access}
