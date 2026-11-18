from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import ROLES, User
from ..services import settings as settings_svc
from ..services.auth import hash_password, require_roles, verify_csrf
from ..templating import render

router = APIRouter(prefix="/admin")
manager = require_roles()


def _settings_ctx(db: Session) -> dict:
    return {k: settings_svc.get(db, k) for k in ("public_base_url", "service_tel", "default_warranty_months")}


@router.get("/settings")
def settings_form(request: Request, saved: int = 0, db: Session = Depends(get_db), user: User = Depends(manager)):
    return render(request, "admin_settings.html", user, s=_settings_ctx(db), saved=saved, errors=[],
                  need_confirm=False)


@router.post("/settings", dependencies=[Depends(verify_csrf)])
def settings_save(request: Request, db: Session = Depends(get_db), user: User = Depends(manager),
                  public_base_url: str = Form(""), service_tel: str = Form(""),
                  default_warranty_months: str = Form(""), confirm_url_change: str = Form("")):
    new = {"public_base_url": public_base_url.strip().rstrip("/"), "service_tel": service_tel.strip(),
           "default_warranty_months": default_warranty_months.strip()}
    errors = []
    url = new["public_base_url"]
    if url and not (url.startswith("https://") or url.startswith("http://")):
        errors.append("對外網址必須以 https:// 或 http:// 開頭")
    if not new["service_tel"]:
        errors.append("請填寫叫修電話")
    if not (new["default_warranty_months"].isdigit() and int(new["default_warranty_months"]) <= 600):
        errors.append("預設保固月數必須是 0 到 600 之間的整數")
    old_url = settings_svc.get(db, "public_base_url")
    need_confirm = bool(old_url) and url != old_url and confirm_url_change != "yes"
    if errors or need_confirm:
        return render(request, "admin_settings.html", user, s=new, saved=0, errors=errors,
                      need_confirm=need_confirm, status_code=400)
    for k, v in new.items():
        settings_svc.put(db, k, v)
    db.commit()
    return RedirectResponse("/admin/settings?saved=1", status_code=303)


@router.get("/users")
def users_page(request: Request, db: Session = Depends(get_db), user: User = Depends(manager)):
    users = list(db.scalars(select(User).order_by(User.id)))
    return render(request, "admin_users.html", user, users=users, roles=ROLES, error=None)


@router.post("/users", dependencies=[Depends(verify_csrf)])
def user_create(request: Request, db: Session = Depends(get_db), user: User = Depends(manager),
                email: str = Form(""), name: str = Form(""), role: str = Form(""), password: str = Form("")):
    email = email.strip().lower()
    error = None
    if "@" not in email or not name.strip():
        error = "請填寫姓名與正確的 Email"
    elif role not in ROLES:
        error = "角色不正確"
    elif len(password) < 8:
        error = "密碼至少 8 個字元"
    elif db.scalar(select(User).where(User.email == email)):
        error = "這個 Email 已經有帳號"
    if error:
        users = list(db.scalars(select(User).order_by(User.id)))
        return render(request, "admin_users.html", user, users=users, roles=ROLES, error=error, status_code=400)
    db.add(User(email=email, name=name.strip(), role=role, password_hash=hash_password(password)))
    db.commit()
    return RedirectResponse("/admin/users", status_code=303)


@router.post("/users/{user_id}", dependencies=[Depends(verify_csrf)])
def user_update(user_id: int, db: Session = Depends(get_db), user: User = Depends(manager),
                action: str = Form(""), role: str = Form(""), password: str = Form("")):
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404)
    if action == "toggle":
        if target.id == user.id:
            raise HTTPException(status_code=400, detail="不能停用自己的帳號")
        target.is_active = not target.is_active
    elif action == "role":
        if role not in ROLES:
            raise HTTPException(status_code=400, detail="角色不正確")
        if target.id == user.id and role != "manager":
            raise HTTPException(status_code=400, detail="不能把自己降為非負責人")
        target.role = role
    elif action == "password":
        if len(password) < 8:
            raise HTTPException(status_code=400, detail="密碼至少 8 個字元")
        target.password_hash = hash_password(password)
    else:
        raise HTTPException(status_code=400, detail="未知的操作")
    db.commit()
    return RedirectResponse("/admin/users", status_code=303)
