"""Device creation (FR-01..FR-08, FR-10). Kept out of routers so future imports can reuse it."""
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Batch, Device
from . import settings as settings_svc
from .qr_payload import (QR_FIELD_CHOICES, PayloadTooLarge, build_payload, new_scan_code)
from .serials import SerialError, check_quantity, parse_serials
from .warranty import warranty_end


@dataclass
class DeviceInput:
    model: str = ""
    spec: str = ""
    ship_date: str = ""
    qty: str = ""
    cust_po: str = ""
    int_po: str = ""
    customer_name: str = ""
    warranty_months: str = ""
    warranty_start: str = ""
    serials: str = ""
    qr_fields: list[str] = field(default_factory=list)
    label_size: str = "60x40"


@dataclass
class Plan:
    errors: list[str]
    rows: list[dict]  # one per device: fields + qr_payload


def _parse_date(value: str, label: str, errors: list[str]) -> date | None:
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        errors.append(f"請填寫{label}（格式 YYYY-MM-DD）")
        return None


def _unique_scan_codes(db: Session, n: int) -> list[str]:
    codes: set[str] = set()
    while len(codes) < n:
        batch = {new_scan_code() for _ in range(n - len(codes))} - codes
        taken = set(db.scalars(select(Device.scan_code).where(Device.scan_code.in_(batch))))
        codes |= batch - taken
    return list(codes)


def plan_batch(db: Session, data: DeviceInput) -> Plan:
    """Validate input and compute every device's row and QR text. Writes nothing."""
    errors: list[str] = []
    service_tel = settings_svc.get(db, "service_tel").strip()
    if not service_tel:
        errors.append("尚未設定叫修電話，請先到「系統設定」填寫")
    model = data.model.strip()
    if not model:
        errors.append("請填寫型號")
    cust_po, int_po = data.cust_po.strip(), data.int_po.strip()
    if not cust_po:
        errors.append("請填寫客戶訂單編號")
    if not int_po:
        errors.append("請填寫內部訂單編號")
    ship = _parse_date(data.ship_date, "出貨日期", errors)

    qty = None
    if data.qty.strip().isdigit() and int(data.qty) >= 1:
        qty = int(data.qty)
    else:
        errors.append("數量必須是正整數")

    months = None
    raw_months = data.warranty_months.strip() or settings_svc.get(db, "default_warranty_months")
    if raw_months.isdigit() and 0 <= int(raw_months) <= 600:
        months = int(raw_months)
    else:
        errors.append("保固長度必須是 0 到 600 之間的整數（月）")

    w_start = ship
    if data.warranty_start.strip():
        w_start = _parse_date(data.warranty_start, "保固開始日", errors)

    fields = [f for f in data.qr_fields if f in QR_FIELD_CHOICES]

    serials: list[str] = []
    try:
        serials = parse_serials(data.serials)
        if not serials:
            errors.append("請填寫序號")
        elif qty is not None:
            check_quantity(serials, qty)
    except SerialError as e:
        errors.append(str(e))

    if serials:
        existing = list(db.scalars(select(Device.serial).where(Device.serial.in_(serials))))
        if existing:
            more = " …" if len(existing) > 5 else ""
            errors.append(f"序號已存在於台帳：{', '.join(sorted(existing)[:5])}{more}")

    if errors:
        return Plan(errors=errors, rows=[])

    w_end = warranty_end(w_start, months)
    base_url = settings_svc.get(db, "public_base_url")
    codes = _unique_scan_codes(db, len(serials))
    rows = []
    try:
        for serial, code in zip(serials, codes):
            payload = build_payload(
                model=model, serial=serial, service_tel=service_tel, spec=data.spec,
                ship_date=ship, cust_po=cust_po, int_po=int_po, warranty_start=w_start,
                warranty_end=w_end, qr_fields=fields, public_base_url=base_url, scan_code=code)
            rows.append(dict(
                serial=serial, scan_code=code, model=model, spec=data.spec.strip("\n"),
                ship_date=ship, cust_po=cust_po, int_po=int_po,
                customer_name=data.customer_name.strip(), warranty_months=months,
                warranty_start=w_start, warranty_end=w_end, service_tel=service_tel,
                qr_fields=fields, qr_payload=payload))
    except PayloadTooLarge as e:
        return Plan(errors=[str(e)], rows=[])
    return Plan(errors=[], rows=rows)


def create_batch(db: Session, data: DeviceInput, user_id: int | None) -> tuple[Batch | None, list[str]]:
    """All-or-nothing: any validation error creates no devices."""
    plan = plan_batch(db, data)
    if plan.errors:
        return None, plan.errors
    batch = Batch(created_by=user_id, label_size=data.label_size or "60x40")
    db.add(batch)
    for row in plan.rows:
        batch.devices.append(Device(**row))
    db.commit()
    return batch, []
