import json
import re
from datetime import date

from sqlalchemy import func, select

from app.models import Device

from .conftest import device_form, login


def _count(db):
    db.expire_all()
    return db.scalar(select(func.count()).select_from(Device))


def _set_base_url(client, token, url, confirm=None):
    data = {"csrf_token": token, "service_tel": "0800-123-456", "default_warranty_months": "12",
            "public_base_url": url}
    if confirm:
        data["confirm_url_change"] = "yes"
    return client.post("/admin/settings", data=data, follow_redirects=False)


def test_service_tel_required_before_creating(client, db):
    token = login(client)
    r = client.post("/devices", data=device_form(token))
    assert r.status_code == 422 and "叫修電話" in r.json()["errors"][0]
    assert _count(db) == 0
    assert "尚未設定叫修電話" in client.get("/devices/new").text


def test_create_fifty_devices(admin, db):
    client, token = admin
    r = client.post("/devices", data=device_form(token, qty="50", serials="SN0001~SN0050"))
    assert r.status_code == 200 and r.json()["redirect"] == "/batches/1"
    assert _count(db) == 50
    d = db.scalar(select(Device).where(Device.serial == "SN0007"))
    assert d.qr_payload == "型號:XYZ-200\n序號:SN0007\n叫修電話:0800-123-456"
    assert d.warranty_start == date(2026, 11, 16) and d.warranty_end == date(2027, 11, 16)
    assert len(set(db.scalars(select(Device.scan_code)))) == 50


def test_preview_writes_nothing(admin, db):
    client, token = admin
    r = client.post("/devices/preview", data=device_form(token))
    assert r.status_code == 200 and r.json()["count"] == 3
    assert _count(db) == 0


def test_existing_serial_blocks_whole_batch(admin, db):
    client, token = admin
    client.post("/devices", data=device_form(token))
    r = client.post("/devices", data=device_form(token, qty="3", serials="SN0003~SN0005"))
    assert r.status_code == 422 and "SN0003" in r.json()["errors"][0]
    assert _count(db) == 3


def test_quantity_mismatch(admin, db):
    client, token = admin
    r = client.post("/devices", data=device_form(token, qty="4"))
    assert r.status_code == 422 and "不符" in r.json()["errors"][0]
    assert _count(db) == 0


def test_checked_fields_and_multiline_spec(admin, db):
    client, token = admin
    data = device_form(token, qty="1", serials="A1", spec="電壓 24V\r\n黑色外殼\r\n")
    data["qr_fields"] = ["spec", "int_po"]
    assert client.post("/devices", data=data).status_code == 200
    d = db.scalar(select(Device))
    assert d.qr_payload == "型號:XYZ-200\n序號:A1\n叫修電話:0800-123-456\n規格:\n電壓 24V\n黑色外殼\n內部訂單:SO-2026-1116-01"


def test_manual_warranty_start(admin, db):
    client, token = admin
    client.post("/devices", data=device_form(token, qty="1", serials="A1", warranty_start="2026-12-01",
                                             warranty_months="24"))
    d = db.scalar(select(Device))
    assert d.warranty_start == date(2026, 12, 1) and d.warranty_end == date(2028, 12, 1)


def test_oversized_payload_blocked(admin, db):
    client, token = admin
    data = device_form(token, qty="1", serials="A1", spec="規格" * 600)
    data["qr_fields"] = ["spec"]
    r = client.post("/devices", data=data)
    assert r.status_code == 422 and "QR 內容太多" in r.json()["errors"][0]
    assert _count(db) == 0


def test_base_url_adds_repair_line_and_change_needs_confirm(admin, db):
    client, token = admin
    assert _set_base_url(client, token, "https://s.example.com/").status_code == 303
    client.post("/devices", data=device_form(token, qty="1", serials="A1"))
    d = db.scalar(select(Device))
    assert d.qr_payload.split("\n")[-1] == f"線上報修:https://s.example.com/d/{d.scan_code}"
    r = _set_base_url(client, token, "https://other.example.com")
    assert r.status_code == 400 and "舊網域必須保留" in r.text
    assert _set_base_url(client, token, "https://other.example.com", confirm=True).status_code == 303


def test_edit_keeps_payload_and_flags_stale_then_regenerate(admin, db):
    client, token = admin
    client.post("/devices", data=device_form(token, qty="1", serials="A1"))
    d = db.scalar(select(Device))
    original = d.qr_payload
    assert "與已印出的 QR 內容不同" not in client.get(f"/devices/{d.id}").text
    r = client.post(f"/devices/{d.id}", data={"csrf_token": token, "model": "NEW-9", "spec": "", "note": "",
                    "ship_date": "2026-11-16", "cust_po": "PO-889012", "int_po": "SO-2026-1116-01",
                    "customer_name": "", "warranty_months": "12", "warranty_start": "2026-11-16"},
                    follow_redirects=False)
    assert r.status_code == 303
    db.expire_all()
    d = db.get(Device, d.id)
    assert d.model == "NEW-9" and d.qr_payload == original
    assert "與已印出的 QR 內容不同" in client.get(f"/devices/{d.id}").text
    # Reprint page still carries the original text.
    assert "XYZ-200" in client.get(f"/devices/{d.id}/label").text
    assert client.post(f"/devices/{d.id}/regenerate-qr", data={"csrf_token": token}).status_code == 400
    assert client.post(f"/devices/{d.id}/regenerate-qr", data={"csrf_token": token, "confirm": "yes"},
                       follow_redirects=False).status_code == 303
    db.expire_all()
    assert "型號:NEW-9" in db.get(Device, d.id).qr_payload


def test_search(admin):
    client, token = admin
    client.post("/devices", data=device_form(token))
    assert "SN0002" in client.get("/devices?q=PO-889").text
    assert "SN0002" in client.get("/devices?q=大同").text
    assert "找不到符合的設備" in client.get("/devices?q=zzz").text


def test_label_page_embeds_stored_payloads(admin, db):
    client, token = admin
    client.post("/devices", data=device_form(token))
    html = client.get("/batches/1").text
    rows = json.loads(re.search(r'<script id="rows" type="application/json">(.*?)</script>', html, re.S).group(1))
    stored = {d.serial: d.qr_payload for d in db.scalars(select(Device))}
    assert {r["serial"]: r["payload"] for r in rows} == stored and len(stored) == 3
