import re

import pytest
from fastapi.testclient import TestClient

ADMIN = ("boss@example.com", "admin-pass-123")


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("INITIAL_ADMIN_EMAIL", ADMIN[0])
    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", ADMIN[1])
    from app.main import create_app
    return create_app()


@pytest.fixture()
def db(app):
    from app.db import SessionLocal
    with SessionLocal() as s:
        yield s


def csrf(client: TestClient, path: str = "/login") -> str:
    html = client.get(path).text
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)


def login(client: TestClient, email: str = ADMIN[0], password: str = ADMIN[1]) -> str:
    token = csrf(client)
    r = client.post("/login", data={"email": email, "password": password, "csrf_token": token},
                    follow_redirects=False)
    assert r.status_code == 303, r.text
    return csrf(client, "/devices/new") if email == ADMIN[0] else token


@pytest.fixture()
def client(app):
    return TestClient(app)


@pytest.fixture()
def admin(client):
    """Logged-in manager client with service phone configured. Returns (client, csrf_token)."""
    token = login(client)
    r = client.post("/admin/settings", data={"csrf_token": token, "service_tel": "0800-123-456",
                                             "default_warranty_months": "12", "public_base_url": ""},
                    follow_redirects=False)
    assert r.status_code == 303
    return client, token


def device_form(token: str, **over) -> dict:
    data = {"csrf_token": token, "model": "XYZ-200", "spec": "", "ship_date": "2026-11-16", "qty": "3",
            "cust_po": "PO-889012", "int_po": "SO-2026-1116-01", "customer_name": "大同客戶",
            "warranty_months": "12", "warranty_start": "", "serials": "SN0001~SN0003",
            "label_size": "60x40"}
    data.update(over)
    return data
