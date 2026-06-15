"""Pydantic schemas for API request/response validation."""

from decimal import Decimal
from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    """Registration payload."""

    email: str = Field(..., description="Email address")
    password: str = Field(..., min_length=8, description="Password (min 8 characters)")
    first_name: str = Field(..., max_length=30)
    last_name: str = Field(..., max_length=30)


class RegisterResponse(BaseModel):
    """Registration response."""

    id: str
    email: str
    number: str


class TokenRequest(BaseModel):
    """Login payload."""

    email: str
    password: str


class TokenResponse(BaseModel):
    """JWT token pair."""

    access: str
    refresh: str


class RefreshTokenRequest(BaseModel):
    """Refresh token payload."""

    refresh: str


class DepositRequest(BaseModel):
    """Deposit initiation payload."""

    amount: Decimal = Field(
        ..., gt=0, decimal_places=2, description="Deposit amount in Naira"
    )
    callback_url: str | None = Field(
        None,
        description="URL to redirect the user to after Paystack payment. "
        "Falls back to settings.CALLBACK_URL if not provided.",
    )


class DepositResponse(BaseModel):
    """Deposit initiation response with Paystack URL."""

    authorization_url: str
    reference: str


class TransactionStatusResponse(BaseModel):
    """Transaction status for verification after Paystack redirect."""

    reference: str
    status: str
    amount: Decimal
    type: str
    paid_at: str | None = None
    created_at: str


class WithdrawRequest(BaseModel):
    """Withdrawal payload."""

    amount: Decimal = Field(
        ..., gt=0, decimal_places=2, description="Withdrawal amount in Naira"
    )


class TransferRequest(BaseModel):
    """Transfer payload."""

    recipient_account_number: str = Field(..., min_length=6, max_length=6)
    amount: Decimal = Field(..., gt=0, decimal_places=2)


class BalanceResponse(BaseModel):
    """Balance output."""

    balance: Decimal


class MessageResponse(BaseModel):
    """Generic message with updated balance."""

    message: str
    new_balance: Decimal


class UserOut(BaseModel):
    """User profile output."""

    id: str
    email: str
    first_name: str
    last_name: str
    is_admin: bool
    number: str
    balance: Decimal


class AdminUserOut(BaseModel):
    """Admin-facing user output."""

    id: str
    email: str
    first_name: str
    last_name: str
    is_admin: bool
    number: str
    balance: Decimal
