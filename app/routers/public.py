"""Customer-facing pages. No login. Only fields allowed by docs/05-routes.md may appear."""
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Device, User
from ..services import settings as settings_svc
from ..services.auth import current_user_optional
from ..services.qr_payload import SCAN_ALPHABET, SCAN_CODE_LEN
from ..services.warranty import in_warranty
from ..templating import render

router = APIRouter()
_CODE = re.compile(f"^[{SCAN_ALPHABET}]{{{SCAN_CODE_LEN}}}$")


@router.get("/d/{scan_code}")
def device_page(scan_code: str, request: Request, db: Session = Depends(get_db),
                user: User | None = Depends(current_user_optional)):
    code = scan_code.upper()
    device = db.scalar(select(Device).where(Device.scan_code == code)) if _CODE.match(code) else None
    if device is None:
        raise HTTPException(status_code=404)
    if user is not None:
        return RedirectResponse(f"/devices/{device.id}", status_code=303)

    fields = set(device.qr_fields or [])
    # Build the public view explicitly; never pass the Device object to the template.
    view = {
        "model": device.model,
        "serial": device.serial,
        "in_warranty": in_warranty(device.warranty_end),
        "service_tel": settings_svc.get(db, "service_tel") or device.service_tel,
        "spec_lines": [l for l in device.spec.splitlines() if l.strip()] if "spec" in fields else [],
        "ship_date": device.ship_date.isoformat() if "ship_date" in fields else None,
        "cust_po": device.cust_po if "cust_po" in fields else None,
        "int_po": device.int_po if "int_po" in fields else None,
        "warranty": (f"{device.warranty_start.isoformat()} ~ {device.warranty_end.isoformat()}"
                     if "warranty" in fields else None),
    }
    resp = render(request, "public_device.html", d=view)
    resp.headers["X-Robots-Tag"] = "noindex"
    return resp
