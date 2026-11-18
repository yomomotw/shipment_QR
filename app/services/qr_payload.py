"""The single place that assembles QR text. Format: docs/04-qr-label-spec.md.

The first three lines are always present so the QR stays readable offline.
"""
import secrets
from datetime import date

SCAN_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
SCAN_CODE_LEN = 8
QR_FIELD_CHOICES = ("spec", "ship_date", "cust_po", "int_po", "warranty")
QR_FIELD_LABELS = {
    "spec": "規格", "ship_date": "出貨日期", "cust_po": "客戶訂單號",
    "int_po": "內部訂單號", "warranty": "保固期間",
}
# QR version 40, error correction M, byte mode.
MAX_PAYLOAD_BYTES = 2331


class PayloadTooLarge(ValueError):
    pass


def new_scan_code() -> str:
    return "".join(secrets.choice(SCAN_ALPHABET) for _ in range(SCAN_CODE_LEN))


def _clean_spec(spec: str) -> list[str]:
    lines = (spec or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def build_payload(*, model: str, serial: str, service_tel: str, spec: str = "",
                  ship_date: date | None = None, cust_po: str = "", int_po: str = "",
                  warranty_start: date | None = None, warranty_end: date | None = None,
                  qr_fields=(), public_base_url: str = "", scan_code: str = "") -> str:
    lines = [f"型號:{model}", f"序號:{serial}", f"叫修電話:{service_tel}"]
    fields = set(qr_fields or ())
    if "spec" in fields:
        spec_lines = _clean_spec(spec)
        if spec_lines:
            lines.append("規格:")
            lines.extend(spec_lines)
    if "ship_date" in fields and ship_date:
        lines.append(f"出貨日期:{ship_date.isoformat()}")
    if "cust_po" in fields and cust_po:
        lines.append(f"客戶訂單:{cust_po}")
    if "int_po" in fields and int_po:
        lines.append(f"內部訂單:{int_po}")
    if "warranty" in fields and warranty_start and warranty_end:
        lines.append(f"保固:{warranty_start.isoformat()}~{warranty_end.isoformat()}")
    base = (public_base_url or "").strip().rstrip("/")
    if base and scan_code:
        lines.append(f"線上報修:{base}/d/{scan_code}")
    payload = "\n".join(lines)
    size = len(payload.encode("utf-8"))
    if size > MAX_PAYLOAD_BYTES:
        raise PayloadTooLarge(
            f"QR 內容太多（{size} bytes，上限 {MAX_PAYLOAD_BYTES}），請減少勾選的資料或縮短規格")
    return payload


def payload_for_device(device, public_base_url: str) -> str:
    return build_payload(
        model=device.model, serial=device.serial, service_tel=device.service_tel,
        spec=device.spec, ship_date=device.ship_date, cust_po=device.cust_po,
        int_po=device.int_po, warranty_start=device.warranty_start,
        warranty_end=device.warranty_end, qr_fields=device.qr_fields,
        public_base_url=public_base_url, scan_code=device.scan_code)
