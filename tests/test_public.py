from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models import Device

from .conftest import device_form


def _make(admin, db, **over):
    client, token = admin
    data = device_form(token, qty="1", serials="A1", spec="電壓 24V", **over)
    data["qr_fields"] = over.pop("qr_fields", [])
    assert client.post("/devices", data=data).status_code == 200
    return db.scalar(select(Device))


def test_public_page_hides_unchecked_fields(admin, db, app):
    d = _make(admin, db)
    r = TestClient(app).get(f"/d/{d.scan_code}")
    assert r.status_code == 200 and r.headers["x-robots-tag"] == "noindex"
    assert "XYZ-200" in r.text and "A1" in r.text and "0800-123-456" in r.text and "保固內" in r.text
    for secret in ("SO-2026-1116-01", "PO-889012", "大同客戶", "電壓 24V", "2026-11-16"):
        assert secret not in r.text, secret


def test_public_page_shows_checked_fields_only(admin, db, app):
    client, token = admin
    data = device_form(token, qty="1", serials="A1", spec="電壓 24V")
    data["qr_fields"] = ["spec", "cust_po"]
    client.post("/devices", data=data)
    d = db.scalar(select(Device))
    text = TestClient(app).get(f"/d/{d.scan_code}").text
    assert "電壓 24V" in text and "PO-889012" in text
    assert "SO-2026-1116-01" not in text and "大同客戶" not in text


def test_unknown_and_malformed_codes_look_identical(app):
    c = TestClient(app)
    a, b = c.get("/d/ZZZZZZZZ"), c.get("/d/not-a-code!")
    assert a.status_code == b.status_code == 404
    assert a.text == b.text


def test_serial_cannot_be_used_as_code(admin, db, app):
    _make(admin, db)
    assert TestClient(app).get("/d/A1").status_code == 404


def test_logged_in_staff_redirected_to_backend(admin, db):
    client, _ = admin
    d = _make(admin, db)
    r = client.get(f"/d/{d.scan_code}", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == f"/devices/{d.id}"


def test_spec_is_escaped(admin, db, app):
    client, token = admin
    data = device_form(token, qty="1", serials="A1", spec="<script>alert(1)</script>")
    data["qr_fields"] = ["spec"]
    client.post("/devices", data=data)
    d = db.scalar(select(Device))
    text = TestClient(app).get(f"/d/{d.scan_code}").text
    assert "<script>alert(1)</script>" not in text and "&lt;script&gt;" in text
