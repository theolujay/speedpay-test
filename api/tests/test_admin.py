import pytest

pytestmark = pytest.mark.django_db


class TestAdminUsers:
    def test_admin_list_users(
        self, client, admin_user, admin_account, admin_auth_headers, user, account
    ):
        resp = client.get("/admin/users", headers=admin_auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) >= 2
        emails = {u["email"] for u in body}
        assert "admin@example.com" in emails
        assert "alice@example.com" in emails

    def test_admin_users_shows_balances(
        self, client, admin_user, admin_auth_headers, account
    ):
        account.balance = 5000
        account.save()

        resp = client.get("/admin/users", headers=admin_auth_headers)
        body = resp.json()
        alice = next(u for u in body if u["email"] == "alice@example.com")
        assert alice["number"] == account.number
        assert alice["balance"] is not None

    def test_non_admin_forbidden(self, client, user, auth_headers):
        resp = client.get("/admin/users", headers=auth_headers)
        assert resp.status_code == 403

    def test_no_auth(self, client):
        resp = client.get("/admin/users")
        assert resp.status_code == 401
