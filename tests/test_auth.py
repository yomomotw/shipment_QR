from sqlalchemy import select

from app.models import User

from .conftest import csrf, login


def test_healthz(client):
    assert client.get("/healthz").json() == {"status": "ok"}


def test_backend_requires_login(client):
    for path in ("/devices", "/devices/new", "/admin/settings", "/admin/users", "/"):
        r = client.get(path, follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"].startswith("/login"), path


def test_wrong_password(client):
    r = client.post("/login", data={"email": "boss@example.com", "password": "nope", "csrf_token": csrf(client)})
    assert r.status_code == 401


def test_post_without_csrf_rejected(client):
    r = client.post("/login", data={"email": "boss@example.com", "password": "admin-pass-123"})
    assert r.status_code == 400


def _add_user(client, token, email, role):
    r = client.post("/admin/users", data={"csrf_token": token, "name": role, "email": email, "role": role,
                                          "password": "password-1"}, follow_redirects=False)
    assert r.status_code == 303


def test_agent_cannot_open_admin(admin, app):
    client, token = admin
    _add_user(client, token, "agent@example.com", "agent")
    from fastapi.testclient import TestClient
    c2 = TestClient(app)
    login(c2, "agent@example.com", "password-1")
    assert c2.get("/devices").status_code == 200
    assert c2.get("/admin/settings").status_code == 403
    assert c2.get("/admin/users").status_code == 403


def test_engineer_cannot_create_devices(admin, app):
    client, token = admin
    _add_user(client, token, "eng@example.com", "engineer")
    from fastapi.testclient import TestClient
    c2 = TestClient(app)
    login(c2, "eng@example.com", "password-1")
    assert c2.get("/devices/new").status_code == 403


def test_disabled_account_cannot_login(admin, app, db):
    client, token = admin
    _add_user(client, token, "agent@example.com", "agent")
    uid = db.scalar(select(User.id).where(User.email == "agent@example.com"))
    assert client.post(f"/admin/users/{uid}", data={"csrf_token": token, "action": "toggle"},
                       follow_redirects=False).status_code == 303
    from fastapi.testclient import TestClient
    c2 = TestClient(app)
    r = c2.post("/login", data={"email": "agent@example.com", "password": "password-1", "csrf_token": csrf(c2)})
    assert r.status_code == 401


def test_passwords_are_hashed(admin, db):
    user = db.scalar(select(User))
    assert "admin-pass-123" not in user.password_hash and user.password_hash.startswith("$argon2")
