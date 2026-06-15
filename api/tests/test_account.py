from decimal import Decimal
from unittest.mock import patch

import pytest

from api.models import Transaction

pytestmark = pytest.mark.django_db


class TestBalance:
    def test_get_balance(self, client, account, auth_headers):
        resp = client.get("/account/balance", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["balance"] == "0.00"

    def test_balance_no_auth(self, client):
        resp = client.get("/account/balance")
        assert resp.status_code == 401

    def test_balance_returns_correct_amount(self, client, account, auth_headers):
        account.balance = Decimal("1500.00")
        account.save()
        resp = client.get("/account/balance", headers=auth_headers)
        assert resp.json()["balance"] == "1500.00"


class TestDeposit:
    @patch("api.routes.account.pc.transactions.initialize")
    def test_deposit_success(self, mock_init, client, account, auth_headers):
        mock_init.return_value = (
            {
                "reference": "PAYSTACK_REF_123",
                "authorization_url": "https://paystack.com/checkout/abc",
            },
            None,
        )

        resp = client.post(
            "/account/deposit",
            json={"amount": "5000.00", "callback_url": "https://mysite.com/payments/callback"},
            headers=auth_headers,
        )
        assert resp.status_code == 202
        body = resp.json()
        assert body["authorization_url"] == "https://paystack.com/checkout/abc"
        assert body["reference"] == "PAYSTACK_REF_123"

        mock_init.assert_called_once_with(
            amount=500000,
            email="alice@example.com",
            currency="NGN",
            callback_url="https://mysite.com/payments/callback",
        )

        tx = Transaction.objects.get(reference="PAYSTACK_REF_123")
        assert tx.amount == Decimal("5000.00")
        assert tx.type == Transaction.Type.DEPOSIT
        assert tx.status == Transaction.Status.PENDING

    @patch("api.routes.account.pc.transactions.initialize")
    def test_deposit_without_callback_url(
        self, mock_init, client, account, auth_headers, settings
    ):
        settings.CALLBACK_URL = ""
        mock_init.return_value = (
            {
                "reference": "PAYSTACK_REF_456",
                "authorization_url": "https://paystack.com/checkout/xyz",
            },
            None,
        )

        resp = client.post(
            "/account/deposit", json={"amount": "5000.00"}, headers=auth_headers
        )
        assert resp.status_code == 202
        mock_init.assert_called_once_with(
            amount=500000,
            email="alice@example.com",
            currency="NGN",
            callback_url=None,
        )

    def test_deposit_no_auth(self, client):
        resp = client.post("/account/deposit", json={"amount": "5000.00"})
        assert resp.status_code == 401

    def test_deposit_amount_too_small(self, client, account, auth_headers):
        resp = client.post(
            "/account/deposit", json={"amount": "10.00"}, headers=auth_headers
        )
        assert resp.status_code == 400


class TestTransactionStatus:
    def test_transaction_status_success(
        self, client, account, auth_headers, pending_deposit
    ):
        resp = client.get(
            f"/account/transactions/{pending_deposit.reference}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["reference"] == pending_deposit.reference
        assert body["status"] == "pending"
        assert body["amount"] == "5000.00"
        assert body["type"] == "deposit"

    def test_transaction_status_not_found(self, client, auth_headers):
        resp = client.get(
            "/account/transactions/NONEXISTENT_REF",
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_transaction_status_wrong_user(
        self, client, account, auth_headers, admin_auth_headers, pending_deposit
    ):
        resp = client.get(
            f"/account/transactions/{pending_deposit.reference}",
            headers=admin_auth_headers,
        )
        assert resp.status_code == 400

    def test_transaction_status_no_auth(self, client, pending_deposit):
        resp = client.get(f"/account/transactions/{pending_deposit.reference}")
        assert resp.status_code == 401


class TestWithdraw:
    def test_withdraw_success(self, client, account, auth_headers):
        account.balance = Decimal("10000.00")
        account.save()

        resp = client.post(
            "/account/withdraw", json={"amount": "3000.00"}, headers=auth_headers
        )
        assert resp.status_code == 202
        body = resp.json()
        assert "successful" in body["message"].lower()
        assert body["new_balance"] == "7000.00"

        account.refresh_from_db()
        assert account.balance == Decimal("7000.00")

        tx = Transaction.objects.filter(
            account=account, type=Transaction.Type.WITHDRAWAL
        ).first()
        assert tx is not None
        assert tx.amount == Decimal("3000.00")

    def test_withdraw_insufficient_funds(self, client, account, auth_headers):
        resp = client.post(
            "/account/withdraw", json={"amount": "500.00"}, headers=auth_headers
        )
        assert resp.status_code == 400
        assert "insufficient" in resp.json()["detail"].lower()

    def test_withdraw_no_auth(self, client):
        resp = client.post("/account/withdraw", json={"amount": "100.00"})
        assert resp.status_code == 401

    def test_withdraw_exact_balance(self, client, account, auth_headers):
        account.balance = Decimal("250.00")
        account.save()

        resp = client.post(
            "/account/withdraw", json={"amount": "250.00"}, headers=auth_headers
        )
        assert resp.status_code == 202
        account.refresh_from_db()
        assert account.balance == Decimal("0.00")


class TestTransfer:
    def test_transfer_success(self, client, account, auth_headers, recipient_account):
        account.balance = Decimal("10000.00")
        account.save()

        resp = client.post(
            "/account/transfer",
            json={
                "recipient_account_number": recipient_account.number,
                "amount": "2500.00",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 202
        body = resp.json()
        assert "successful" in body["message"].lower()
        assert body["new_balance"] == "7500.00"

        account.refresh_from_db()
        recipient_account.refresh_from_db()
        assert account.balance == Decimal("7500.00")
        assert recipient_account.balance == Decimal("2500.00")

        transfer_out = Transaction.objects.filter(
            account=account, type=Transaction.Type.TRANSFER_OUT
        ).first()
        transfer_in = Transaction.objects.filter(
            account=recipient_account, type=Transaction.Type.TRANSFER_IN
        ).first()
        assert transfer_out is not None
        assert transfer_in is not None
        assert transfer_out.amount == Decimal("2500.00")
        assert transfer_in.amount == Decimal("2500.00")

    def test_transfer_self(self, client, account, auth_headers):
        account.balance = Decimal("10000.00")
        account.save()

        resp = client.post(
            "/account/transfer",
            json={
                "recipient_account_number": account.number,
                "amount": "100.00",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "own account" in resp.json()["detail"].lower()

    def test_transfer_insufficient_funds(
        self, client, account, auth_headers, recipient_account
    ):
        resp = client.post(
            "/account/transfer",
            json={
                "recipient_account_number": recipient_account.number,
                "amount": "100.00",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "insufficient" in resp.json()["detail"].lower()

    def test_transfer_invalid_recipient(self, client, account, auth_headers):
        account.balance = Decimal("10000.00")
        account.save()

        resp = client.post(
            "/account/transfer",
            json={
                "recipient_account_number": "000000",
                "amount": "100.00",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "not found" in resp.json()["detail"].lower()

    def test_transfer_no_auth(self, client, recipient_account):
        resp = client.post(
            "/account/transfer",
            json={
                "recipient_account_number": recipient_account.number,
                "amount": "100.00",
            },
        )
        assert resp.status_code == 401
