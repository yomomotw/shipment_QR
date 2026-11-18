from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from ..services.auth import authenticate, current_user, current_user_optional, verify_csrf
from ..templating import render

router = APIRouter()


def _safe_next(target: str) -> str:
    return target if target.startswith("/") and not target.startswith("//") else "/"


@router.get("/")
def home(user: User = Depends(current_user)):
    return RedirectResponse("/devices", status_code=303)


@router.get("/login")
def login_form(request: Request, next: str = "/", user: User | None = Depends(current_user_optional)):
    if user:
        return RedirectResponse(_safe_next(next), status_code=303)
    return render(request, "login.html", next=_safe_next(next), error=None)


@router.post("/login", dependencies=[Depends(verify_csrf)])
def login(request: Request, email: str = Form(""), password: str = Form(""), next: str = Form("/"),
          db: Session = Depends(get_db)):
    user = authenticate(db, email, password)
    if user is None:
        return render(request, "login.html", next=_safe_next(next), status_code=401,
                      error="帳號或密碼錯誤，或帳號已停用")
    request.session.clear()
    request.session["uid"] = user.id
    return RedirectResponse(_safe_next(next), status_code=303)


@router.post("/logout", dependencies=[Depends(verify_csrf)])
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
