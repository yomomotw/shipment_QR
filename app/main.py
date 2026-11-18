from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote

from alembic import command
from alembic.config import Config
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from . import config, db
from .models import User
from .routers import admin, auth as auth_router, devices, public
from .services.auth import LoginRequired, hash_password
from .templating import render

ROOT = Path(__file__).resolve().parent.parent


def run_migrations() -> None:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    command.upgrade(cfg, "head")


def ensure_initial_admin() -> None:
    email, password = config.initial_admin()
    with db.SessionLocal() as s:
        if s.scalar(select(func.count()).select_from(User)) or not (email and password):
            return
        s.add(User(email=email.strip().lower(), name="負責人",
                   password_hash=hash_password(password), role="manager"))
        s.commit()


def create_app() -> FastAPI:
    db.init_engine()
    run_migrations()
    ensure_initial_admin()

    app = FastAPI(title="出貨標籤 QR 與設備叫修系統", docs_url=None, redoc_url=None)
    app.add_middleware(SessionMiddleware, secret_key=config.secret_key(), same_site="lax",
                       https_only=config.https_only(), max_age=60 * 60 * 12)
    app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.exception_handler(LoginRequired)
    async def _login_required(request: Request, exc: LoginRequired):
        target = request.url.path + (f"?{request.url.query}" if request.url.query else "")
        return RedirectResponse(f"/login?next={quote(target)}", status_code=303)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException):
        if exc.status_code == 404:
            return render(request, "not_found.html", status_code=404)
        return render(request, "error.html", status_code=exc.status_code,
                      message=str(exc.detail), code=exc.status_code)

    app.include_router(auth_router.router)
    app.include_router(public.router)
    app.include_router(devices.router)
    app.include_router(admin.router)
    return app
