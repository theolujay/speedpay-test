import json
import hashlib
import hmac
from decimal import Decimal

import pytest

from api.models import Transaction

pytestmark = pytest.mark.django_db

SECRET_KEY = "sk_test_abcdefghijklmnopqrstuvwxyz1234567890"


def _sign(raw: str) -> str:
    return hmac.new(SECRET_KEY.encode(), raw.encode(), hashlib.sha512).hexdigest()


def _body(payload: dict) -> str:
    return json.dumps(payload, separators=(",", ":"))


def _build_payload(
    reference: str, status: str = "success", amount: int = 500000
) -> dict:
    return {
        "event": "charge.success",
        "data": {
            "id": 12345,
            "reference": reference,
            "amount": amount,
            "status": status,
            "customer": {"email": "alice@example.com"},
        },
    }


def _post(client, path: str, payload: dict):
    body = _body(payload)
    signature = _sign(body)
    return client.post(path, data=body, headers={"X-Paystack-Signature": signature})


class TestWebhookChargeSuccess:
    def test_webhook_credits_account(self, client, account, settings):
        settings.PAYSTACK_SECRET_KEY = SECRET_KEY
        tx = Transaction.objects.create(
            account=account,
            type=Transaction.Type.DEPOSIT,
            amount=Decimal("5000.00"),
            reference="REF_WEBHOOK_001",
            status=Transaction.Status.PENDING,
        )

        payload = _build_payload("REF_WEBHOOK_001")
        resp = _post(client, "/webhooks/paystack", payload)
        assert resp.status_code == 200

        tx.refresh_from_db()
        assert tx.status == Transaction.Status.SUCCESS
        assert tx.paid_at is not None

        account.refresh_from_db()
        assert account.balance == Decimal("5000.00")

    def test_webhook_already_processed(self, client, account, settings):
        settings.PAYSTACK_SECRET_KEY = SECRET_KEY
        Transaction.objects.create(
            account=account,
            type=Transaction.Type.DEPOSIT,
            amount=Decimal("5000.00"),
            reference="REF_DUP_001",
            status=Transaction.Status.SUCCESS,
        )

        payload = _build_payload("REF_DUP_001")
        resp = _post(client, "/webhooks/paystack", payload)
        assert resp.status_code == 200
        assert "already" in resp.json()["status"]

    def test_webhook_invalid_signature(self, client, settings):
        settings.PAYSTACK_SECRET_KEY = SECRET_KEY
        payload = _build_payload("REF_BAD_001")
        body = _body(payload)

        resp = client.post(
            "/webhooks/paystack",
            data=body,
            headers={"X-Paystack-Signature": "badsignature"},
        )
        assert resp.status_code == 400

    def test_webhook_unknown_transaction(self, client, settings):
        settings.PAYSTACK_SECRET_KEY = SECRET_KEY
        payload = _build_payload("REF_NONEXISTENT")
        resp = _post(client, "/webhooks/paystack", payload)
        assert resp.status_code == 404

    def test_webhook_unrelated_event_is_ignored(self, client, settings):
        settings.PAYSTACK_SECRET_KEY = SECRET_KEY
        payload = {
            "event": "transfer.success",
            "data": {"reference": "TRF_001", "amount": 50000},
        }
        resp = _post(client, "/webhooks/paystack", payload)
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"
