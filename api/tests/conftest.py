from decimal import Decimal

import pytest
from ninja.testing import TestClient

from api.models import User, Account, generate_account_number
from api.auth import create_tokens_for_user
from api.routes import api


@pytest.fixture
def client():
    return TestClient(api)


@pytest.fixture
def user_data():
    return {
        "email": "alice@example.com",
        "password": "strongpass123",
        "first_name": "Alice",
        "last_name": "Wonder",
    }


@pytest.fixture
def user(db, user_data):
    u = User.objects.create_user(**user_data)
    return u


@pytest.fixture
def account(db, user):
    acc = Account.objects.create(user=user, number=generate_account_number())
    return acc


@pytest.fixture
def admin_user(db):
    u = User.objects.create_user(  # type: ignore
        email="admin@example.com",
        password="adminpass123",
        first_name="Admin",
        last_name="User",
    )
    u.is_admin = True
    u.save()
    return u


@pytest.fixture
def admin_account(db, admin_user):
    acc = Account.objects.create(user=admin_user, number=generate_account_number())
    return acc


@pytest.fixture
def auth_headers(user):
    tokens = create_tokens_for_user(user)
    return {"Authorization": f"Bearer {tokens['access']}"}


@pytest.fixture
def admin_auth_headers(admin_user):
    tokens = create_tokens_for_user(admin_user)
    return {"Authorization": f"Bearer {tokens['access']}"}


@pytest.fixture
def recipient_user(db):
    u = User.objects.create_user(  # type: ignore
        email="bob@example.com",
        password="bobpass123",
        first_name="Bob",
        last_name="Builder",
    )
    return u


@pytest.fixture
def recipient_account(db, recipient_user):
    acc = Account.objects.create(user=recipient_user, number=generate_account_number())
    return acc


@pytest.fixture
def pending_deposit(db, account):
    from api.models import Transaction
    return Transaction.objects.create(
        account=account,
        type=Transaction.Type.DEPOSIT,
        amount=Decimal("5000.00"),
        reference="DEPOSIT_REF_TEST",
        status=Transaction.Status.PENDING,
        authorization_url="https://paystack.com/checkout/test",
    )
