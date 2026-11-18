from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates

from .models import ROLE_LABELS
from .services.auth import csrf_token

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
templates.env.globals["ROLE_LABELS"] = ROLE_LABELS


def render(request: Request, name: str, user=None, status_code: int = 200, **ctx):
    ctx.update(user=user, csrf_token=csrf_token(request))
    return templates.TemplateResponse(request, name, ctx, status_code=status_code)
