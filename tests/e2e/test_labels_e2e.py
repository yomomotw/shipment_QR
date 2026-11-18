"""End-to-end: create devices in a real browser, then decode the printed QR codes and compare
them with what the database stored. Needs playwright (with chromium) and opencv; skipped otherwise.

    pip install playwright opencv-python-headless pypdf && playwright install chromium
"""
import io
import os
import socket
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytest.importorskip("playwright")
cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")
from playwright.sync_api import sync_playwright  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
EMAIL, PASSWORD = "boss@example.com", "admin-pass-123"
SHOTS = Path(os.environ.get("E2E_SHOTS", "")) if os.environ.get("E2E_SHOTS") else None


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    data = tmp_path_factory.mktemp("data")
    port = _free_port()
    env = dict(os.environ, DATA_DIR=str(data), SECRET_KEY="e2e", INITIAL_ADMIN_EMAIL=EMAIL,
               INITIAL_ADMIN_PASSWORD=PASSWORD)
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.asgi:app", "--port", str(port)],
                            cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
            break
        except OSError:
            time.sleep(0.1)
    yield base, data / "app.db"
    proc.terminate()
    proc.wait(timeout=10)


def _decode(png: bytes) -> str:
    img = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)
    img = cv2.resize(img, None, fx=2, fy=2, interpolation=cv2.INTER_NEAREST)
    return cv2.QRCodeDetector().detectAndDecode(img)[0]


def _stored(db_path) -> dict:
    with sqlite3.connect(db_path) as con:
        return dict(con.execute("select serial, qr_payload from device"))


def test_create_print_and_decode(server):
    base, db_path = server
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(device_scale_factor=3, viewport={"width": 1400, "height": 1000})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        page.goto(f"{base}/login")
        page.fill("input[name=email]", EMAIL)
        page.fill("input[name=password]", PASSWORD)
        page.click("main button[type=submit]")
        page.wait_for_url("**/devices")
        page.goto(f"{base}/admin/settings")
        page.fill("input[name=service_tel]", "0800-123-456")
        page.fill("input[name=public_base_url]", base)
        page.click("main button[type=submit]")
        page.wait_for_selector(".msg.o")

        page.goto(f"{base}/devices/new")
        page.fill("input[name=model]", "XYZ-200 黑色")
        page.fill("textarea[name=spec]", "電壓 24V\n功率 150W")
        page.fill("input[name=qty]", "12")
        page.fill("input[name=cust_po]", "PO-889012")
        page.fill("input[name=int_po]", "SO-2026-1116-01")
        page.fill("textarea[name=serials]", "SN0001~SN0010\nAB-77,AB-78")
        page.check("input[name=qr_fields][value=spec]")
        page.check("input[name=qr_fields][value=ship_date]")
        assert page.is_disabled("#create")
        page.click("#preview")
        page.wait_for_selector("#msgs .msg.o")
        if SHOTS:
            page.screenshot(path=str(SHOTS / "new.png"), full_page=True)
        page.click("#create")
        page.wait_for_url("**/batches/*")
        page.wait_for_selector(".tag")

        stored = _stored(db_path)
        assert len(stored) == 12
        tags = page.locator(".tag")
        assert tags.count() == 12
        # The label table is exactly: serial, model, service phone.
        assert tags.first.locator("td.k").all_inner_texts() == ["序號", "型號", "叫修電話"]
        label_text = tags.first.inner_text()
        for hidden in ("PO-889012", "SO-2026-1116-01", "電壓", "2026-"):
            assert hidden not in label_text
        for i in (0, 5, 11):
            serial = tags.nth(i).locator("tr.sn td.v").inner_text()
            decoded = _decode(tags.nth(i).locator(".qr").screenshot())
            assert decoded == stored[serial], serial
            assert decoded.split("\n")[1] == f"序號:{serial}"
            assert decoded.split("\n")[-1].startswith(f"線上報修:{base}/d/")
        if SHOTS:
            page.locator("#sheet").screenshot(path=str(SHOTS / "sheet.png"))

        # Nothing overflows its label at two sizes.
        for size in ("60x40", "50x30"):
            page.select_option("#size", size)
            assert page.evaluate("""() => [...document.querySelectorAll('.tag td.v')]
                .every(td => td.scrollWidth <= td.clientWidth + 1)"""), size
        page.select_option("#size", "60x40")

        # Printed page sizes.
        pypdf = pytest.importorskip("pypdf")
        mm = lambda pt: round(float(pt) / 72 * 25.4)
        page.emulate_media(media="print")
        box = pypdf.PdfReader(io.BytesIO(page.pdf(prefer_css_page_size=True))).pages[0].mediabox
        assert (mm(box.width), mm(box.height)) == (210, 297)
        page.emulate_media(media="screen")
        page.select_option("#layout", "single")
        page.emulate_media(media="print")
        reader = pypdf.PdfReader(io.BytesIO(page.pdf(prefer_css_page_size=True)))
        assert len(reader.pages) == 12
        assert (mm(reader.pages[0].mediabox.width), mm(reader.pages[0].mediabox.height)) == (60, 40)
        page.emulate_media(media="screen")

        # Edit a device, then reprint: the QR must still be the original text.
        with sqlite3.connect(db_path) as con:
            dev_id, code = con.execute("select id, scan_code from device where serial='SN0001'").fetchone()
        page.goto(f"{base}/devices/{dev_id}")
        page.fill("input[name=model]", "CHANGED-1")
        page.click("form[action='/devices/%d'] button[type=submit]" % dev_id)
        page.wait_for_selector(".msg.w")
        page.goto(f"{base}/devices/{dev_id}/label")
        page.wait_for_selector(".tag")
        assert _decode(page.locator(".tag .qr").screenshot()) == stored["SN0001"]

        # Public page on a phone, not logged in.
        phone = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2).new_page()
        phone.goto(f"{base}/d/{code}")
        body = phone.inner_text("body")
        assert "SN0001" in body and "0800-123-456" in body and "電壓 24V" in body
        assert "PO-889012" not in body and "SO-2026-1116-01" not in body
        assert phone.get_attribute("a.call", "href") == "tel:0800-123-456"
        if SHOTS:
            phone.screenshot(path=str(SHOTS / "public.png"))
        assert errors == []
        browser.close()
