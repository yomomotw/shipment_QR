"""Environment-driven configuration. See docs/02-architecture.md."""
import os
from pathlib import Path


def data_dir() -> Path:
    d = Path(os.environ.get("DATA_DIR", "./data")).resolve()
    d.mkdir(parents=True, exist_ok=True)
    return d


def secret_key() -> str:
    key = os.environ.get("SECRET_KEY")
    if not key:
        raise RuntimeError("SECRET_KEY environment variable is required")
    return key


def initial_admin() -> tuple[str | None, str | None]:
    return os.environ.get("INITIAL_ADMIN_EMAIL"), os.environ.get("INITIAL_ADMIN_PASSWORD")


def https_only() -> bool:
    return os.environ.get("HTTPS_ONLY", "").lower() in ("1", "true", "yes")
