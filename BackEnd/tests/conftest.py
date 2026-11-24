import os
import tempfile
from pathlib import Path

# Point the app at a throwaway SQLite database *before* anything imports app settings.
_tmp = Path(tempfile.mkdtemp(prefix="hrms_test_"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_tmp / 'test.db').as_posix()}"
os.environ["UPLOAD_DIR"] = str(_tmp / "uploads")
os.environ["SMTP_HOST"] = ""
os.environ["ENVIRONMENT"] = "test"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import ADMIN_EMAIL, ADMIN_PASSWORD, seed_base  # noqa: E402

API = "/api/v1"
EMP_PASSWORD = "Employee@123"


@pytest.fixture(scope="session", autouse=True)
def _schema():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_base(db)
    yield
    engine.dispose()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def login(client: TestClient, email: str, password: str) -> dict:
    r = client.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def admin_headers(client):
    return login(client, ADMIN_EMAIL, ADMIN_PASSWORD)


_counter = {"n": 0}


@pytest.fixture
def make_employee(client, admin_headers):
    """Creates an employee via the API and returns (employee_json, auth_headers)."""

    def _make(basic=30000, doj="2024-01-01", bank=True, role_id=None, **overrides):
        _counter["n"] += 1
        n = _counter["n"]
        body = {
            "first_name": "Test", "last_name": f"User{n}", "email": f"test.user{n}@example.com",
            "date_of_joining": doj, "password": EMP_PASSWORD,
            "salary": {"basic": basic, "hra": basic * 0.4, "special_allowance": 1000},
            **({"bank_account_number": "123456789012", "bank_name": "HDFC Bank"} if bank else {}),
            **overrides,
        }
        if role_id:
            body["role_id"] = role_id
        r = client.post(f"{API}/employees", json=body, headers=admin_headers)
        assert r.status_code == 201, r.text
        emp = r.json()
        return emp, login(client, emp["email"], EMP_PASSWORD)

    return _make
