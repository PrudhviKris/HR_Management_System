from app.core.config import settings
from app.seed import ADMIN_EMAIL, ADMIN_PASSWORD
from tests.conftest import API, EMP_PASSWORD, login


def test_login_returns_token_and_sets_httponly_refresh_cookie(client):
    r = client.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200
    body = r.json()
    assert body["access_token"] and body["user"]["role"] == "Admin"
    cookie = r.headers["set-cookie"]
    assert settings.REFRESH_COOKIE_NAME in cookie and "HttpOnly" in cookie and "SameSite=strict" in cookie


def test_wrong_password_is_generic_and_does_not_leak_user_existence(client):
    a = client.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": "nope"})
    b = client.post(f"{API}/auth/login", json={"email": "ghost@example.com", "password": "nope"})
    assert a.status_code == b.status_code == 401
    assert a.json()["error"]["message"] == b.json()["error"]["message"]


def test_passwords_are_hashed_not_plain(client, make_employee):
    from app.core.database import SessionLocal
    from app.models import User

    emp, _ = make_employee()
    with SessionLocal() as db:
        user = db.get(User, emp["user_id"])
        assert user.password_hash != EMP_PASSWORD and user.password_hash.startswith("$2")


def test_protected_endpoints_require_token(client):
    assert client.get(f"{API}/employees").status_code == 401
    assert client.get(f"{API}/employees", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_refresh_rotates_and_reuse_revokes_everything(client, make_employee):
    emp, _ = make_employee()
    r = client.post(f"{API}/auth/login", json={"email": emp["email"], "password": EMP_PASSWORD})
    old_refresh = r.cookies.get(settings.REFRESH_COOKIE_NAME)
    access = r.json()["access_token"]

    r2 = client.post(f"{API}/auth/refresh")
    assert r2.status_code == 200
    assert r2.cookies.get(settings.REFRESH_COOKIE_NAME) != old_refresh

    # replay the old (rotated) refresh token -> treated as theft
    client.cookies.clear()
    client.cookies.set(settings.REFRESH_COOKIE_NAME, old_refresh, path=f"{API}/auth")
    r3 = client.post(f"{API}/auth/refresh")
    assert r3.status_code == 401 and r3.json()["error"]["code"] == "token_reuse"
    # and the previously issued access token is revoked too
    assert client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {access}"}).status_code == 401


def test_account_lockout_after_repeated_failures(client, make_employee):
    emp, _ = make_employee()
    for _ in range(settings.MAX_FAILED_LOGINS):
        client.post(f"{API}/auth/login", json={"email": emp["email"], "password": "Wrong-pass1"})
    r = client.post(f"{API}/auth/login", json={"email": emp["email"], "password": EMP_PASSWORD})
    assert r.status_code == 401 and r.json()["error"]["code"] == "account_locked"


def test_logout_invalidates_access_token(client, make_employee):
    _, headers = make_employee()
    assert client.post(f"{API}/auth/logout", headers=headers).status_code == 200
    assert client.get(f"{API}/auth/me", headers=headers).status_code == 401


def test_change_password_enforces_policy(client, make_employee):
    _, headers = make_employee()
    weak = client.post(f"{API}/auth/change-password", headers=headers, json={"current_password": EMP_PASSWORD, "new_password": "weak"})
    assert weak.status_code == 422
    ok = client.post(f"{API}/auth/change-password", headers=headers, json={"current_password": EMP_PASSWORD, "new_password": "Better-Pass9"})
    assert ok.status_code == 200
    assert client.get(f"{API}/auth/me", headers=headers).status_code == 401  # old token revoked


def test_deactivated_employee_cannot_login(client, admin_headers, make_employee):
    emp, headers = make_employee()
    r = client.post(f"{API}/employees/{emp['id']}/deactivate", headers=admin_headers, json={"reason": "Resigned"})
    assert r.status_code == 200
    assert client.get(f"{API}/auth/me", headers=headers).status_code == 401
    r = client.post(f"{API}/auth/login", json={"email": emp["email"], "password": EMP_PASSWORD})
    assert r.status_code == 401


def test_forgot_password_never_reveals_account(client):
    a = client.post(f"{API}/auth/forgot-password", json={"email": ADMIN_EMAIL})
    b = client.post(f"{API}/auth/forgot-password", json={"email": "nobody@example.com"})
    assert a.status_code == b.status_code == 200 and a.json() == b.json()


def test_reset_link_is_redacted_in_email_log(client, admin_headers):
    client.post(f"{API}/auth/forgot-password", json={"email": ADMIN_EMAIL})
    logs = client.get(f"{API}/email-logs?template_code=password_reset", headers=admin_headers).json()["items"]
    detail = client.get(f"{API}/email-logs/{logs[0]['id']}", headers=admin_headers).json()
    assert "token=" not in detail["body_html"] and "[link redacted]" in detail["body_html"]


def test_login_helper(client):
    assert "Authorization" in login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
