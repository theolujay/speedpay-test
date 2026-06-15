import pytest

pytestmark = pytest.mark.django_db


class TestRegister:
    def test_register_success(self, client, user_data):
        resp = client.post("/auth/register", json=user_data)
        assert resp.status_code == 200
        body = resp.json()
        assert body["email"] == user_data["email"]
        assert body["id"]
        assert body["number"]
        assert len(body["number"]) == 6

    def test_register_duplicate_email(self, client, user, user_data):
        resp = client.post("/auth/register", json=user_data)
        assert resp.status_code == 400
        assert "already exists" in resp.json()["detail"].lower()

    def test_register_short_password(self, client, user_data):
        data = {**user_data, "password": "short"}
        resp = client.post("/auth/register", json=data)
        assert resp.status_code == 422

    def test_register_creates_account(self, client, user_data):
        resp = client.post("/auth/register", json=user_data)
        body = resp.json()
        from api.models import Account

        account = Account.objects.get(number=body["number"])
        assert account.balance == 0


class TestToken:
    def test_token_success(self, client, user, user_data):
        resp = client.post(
            "/auth/token",
            json={
                "email": user_data["email"],
                "password": user_data["password"],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["access"]
        assert body["refresh"]

    def test_token_wrong_password(self, client, user):
        resp = client.post(
            "/auth/token",
            json={
                "email": user.email,
                "password": "wrongpassword",
            },
        )
        assert resp.status_code == 400
        assert "invalid" in resp.json()["detail"].lower()

    def test_token_nonexistent_user(self, client):
        resp = client.post(
            "/auth/token",
            json={
                "email": "nobody@example.com",
                "password": "somepass123",
            },
        )
        assert resp.status_code == 400

    def test_token_inactive_user(self, client, user):
        user.is_active = False
        user.save()
        resp = client.post(
            "/auth/token",
            json={
                "email": user.email,
                "password": "strongpass123",
            },
        )
        assert resp.status_code == 400


class TestTokenRefresh:
    def test_refresh_success(self, client, user):
        tokens = __import__(
            "api.auth", fromlist=["create_tokens_for_user"]
        ).create_tokens_for_user(user)
        resp = client.post("/auth/token/refresh", json={"refresh": tokens["refresh"]})
        assert resp.status_code == 200
        assert resp.json()["access"]

    def test_refresh_invalid_token(self, client):
        resp = client.post("/auth/token/refresh", json={"refresh": "invalidtoken"})
        assert resp.status_code == 400
