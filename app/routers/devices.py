from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Batch, Device, User
from ..services import settings as settings_svc
from ..services.auth import require_roles, verify_csrf
from ..services.devices import DeviceInput, create_batch, plan_batch
from ..services.qr_payload import (QR_FIELD_CHOICES, QR_FIELD_LABELS, PayloadTooLarge,
                                   payload_for_device)
from ..services.warranty import in_warranty, warranty_end
from ..templating import render

router = APIRouter()
staff = require_roles("agent")
staff_or_engineer = require_roles("agent", "engineer")
manager = require_roles()
LABEL_SIZES = ["50x30", "60x30", "60x40", "70x40", "80x50"]


def _label_rows(devices: list[Device]) -> list[dict]:
    return [dict(id=d.id, serial=d.serial, model=d.model, tel=d.service_tel, payload=d.qr_payload,
                 ship_date=d.ship_date.isoformat(), cust_po=d.cust_po, int_po=d.int_po)
            for d in devices]


async def _input_from_form(request: Request) -> DeviceInput:
    f = await request.form()
    g = lambda k: str(f.get(k) or "")
    size = g("label_size")
    return DeviceInput(
        model=g("model"), spec=g("spec"), ship_date=g("ship_date"), qty=g("qty"),
        cust_po=g("cust_po"), int_po=g("int_po"), customer_name=g("customer_name"),
        warranty_months=g("warranty_months"), warranty_start=g("warranty_start"),
        serials=g("serials"), qr_fields=[str(v) for v in f.getlist("qr_fields")],
        label_size=size if size in LABEL_SIZES else "60x40")


@router.get("/devices")
def device_list(request: Request, q: str = "", db: Session = Depends(get_db), user: User = Depends(staff)):
    stmt = select(Device).order_by(Device.id.desc()).limit(200)
    term = q.strip()
    if term:
        like = f"%{term}%"
        stmt = stmt.where(or_(Device.serial.like(like), Device.cust_po.like(like),
                              Device.int_po.like(like), Device.customer_name.like(like),
                              Device.model.like(like)))
    devices = list(db.scalars(stmt))
    return render(request, "devices_list.html", user, devices=devices, q=term, today=date.today())


@router.get("/devices/new")
def device_new(request: Request, db: Session = Depends(get_db), user: User = Depends(staff)):
    return render(request, "device_new.html", user,
                  service_tel=settings_svc.get(db, "service_tel"),
                  base_url=settings_svc.get(db, "public_base_url"),
                  default_months=settings_svc.get(db, "default_warranty_months"),
                  today=date.today().isoformat(), sizes=LABEL_SIZES,
                  qr_choices=[(k, QR_FIELD_LABELS[k]) for k in QR_FIELD_CHOICES])


@router.post("/devices/preview", dependencies=[Depends(verify_csrf)])
async def device_preview(request: Request, db: Session = Depends(get_db), user: User = Depends(staff)):
    plan = plan_batch(db, await _input_from_form(request))
    if plan.errors:
        return JSONResponse({"ok": False, "errors": plan.errors}, status_code=422)
    return {"ok": True, "count": len(plan.rows),
            "sample": plan.rows[0]["qr_payload"],
            "first": {"serial": plan.rows[0]["serial"], "model": plan.rows[0]["model"],
                      "tel": plan.rows[0]["service_tel"], "payload": plan.rows[0]["qr_payload"]},
            # Longest payload decides density; send it for the client-side module-size check.
            "longest": max((r["qr_payload"] for r in plan.rows), key=lambda p: len(p.encode("utf-8"))),
            "warranty_end": plan.rows[0]["warranty_end"].isoformat()}


@router.post("/devices", dependencies=[Depends(verify_csrf)])
async def device_create(request: Request, db: Session = Depends(get_db), user: User = Depends(staff)):
    batch, errors = create_batch(db, await _input_from_form(request), user.id)
    if errors:
        return JSONResponse({"ok": False, "errors": errors}, status_code=422)
    return {"ok": True, "redirect": f"/batches/{batch.id}"}


@router.get("/batches/{batch_id}")
def batch_page(batch_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(staff)):
    batch = db.get(Batch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404)
    return render(request, "labels.html", user, title=f"第 {batch.id} 批標籤",
                  rows=_label_rows(batch.devices), size=batch.label_size, sizes=LABEL_SIZES,
                  export_name=f"batch{batch.id}")


@router.get("/devices/{device_id}/label")
def device_label(device_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(staff)):
    device = db.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404)
    size = device.batch.label_size if device.batch else "60x40"
    return render(request, "labels.html", user, title=f"補印標籤 {device.serial}",
                  rows=_label_rows([device]), size=size, sizes=LABEL_SIZES, export_name=device.serial)


@router.get("/devices/{device_id}")
def device_detail(device_id: int, request: Request, saved: int = 0, db: Session = Depends(get_db),
                  user: User = Depends(staff_or_engineer)):
    device = db.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404)
    base_url = settings_svc.get(db, "public_base_url")
    try:
        stale = payload_for_device(device, base_url) != device.qr_payload
    except PayloadTooLarge:
        stale = True
    return render(request, "device_detail.html", user, d=device, stale=stale, saved=saved,
                  in_warranty=in_warranty(device.warranty_end), row=_label_rows([device])[0],
                  qr_labels=[QR_FIELD_LABELS[k] for k in QR_FIELD_CHOICES if k in (device.qr_fields or [])],
                  public_url=(f"{base_url.rstrip('/')}/d/{device.scan_code}" if base_url else ""),
                  can_edit=user.role in ("manager", "agent"), errors=[])


@router.post("/devices/{device_id}", dependencies=[Depends(verify_csrf)])
def device_update(device_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(staff),
                  model: str = Form(""), spec: str = Form(""), ship_date: str = Form(""),
                  cust_po: str = Form(""), int_po: str = Form(""), customer_name: str = Form(""),
                  warranty_months: str = Form(""), warranty_start: str = Form(""), note: str = Form("")):
    """Edits data only. serial, scan_code and qr_payload are never changed here."""
    device = db.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404)
    errors = []
    if not model.strip():
        errors.append("請填寫型號")
    try:
        ship = date.fromisoformat(ship_date)
        start = date.fromisoformat(warranty_start)
    except ValueError:
        errors.append("日期格式須為 YYYY-MM-DD")
    if not (warranty_months.isdigit() and int(warranty_months) <= 600):
        errors.append("保固長度必須是 0 到 600 之間的整數（月）")
    if errors:
        raise HTTPException(status_code=400, detail="；".join(errors))
    device.model, device.spec = model.strip(), spec.replace("\r\n", "\n").strip("\n")
    device.ship_date, device.cust_po, device.int_po = ship, cust_po.strip(), int_po.strip()
    device.customer_name, device.note = customer_name.strip(), note.strip()
    device.warranty_months, device.warranty_start = int(warranty_months), start
    device.warranty_end = warranty_end(start, int(warranty_months))
    db.commit()
    return RedirectResponse(f"/devices/{device.id}?saved=1", status_code=303)


@router.post("/devices/{device_id}/regenerate-qr", dependencies=[Depends(verify_csrf)])
def device_regenerate(device_id: int, db: Session = Depends(get_db), user: User = Depends(manager),
                      confirm: str = Form("")):
    device = db.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404)
    if confirm != "yes":
        raise HTTPException(status_code=400, detail="請勾選確認後再重新產生")
    tel = settings_svc.get(db, "service_tel").strip() or device.service_tel
    device.service_tel = tel
    try:
        device.qr_payload = payload_for_device(device, settings_svc.get(db, "public_base_url"))
    except PayloadTooLarge as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    stamp = f"{date.today().isoformat()} 由 {user.name} 重新產生 QR，舊標籤需換貼"
    device.note = f"{device.note}\n{stamp}".strip()
    db.commit()
    return RedirectResponse(f"/devices/{device.id}?saved=2", status_code=303)
