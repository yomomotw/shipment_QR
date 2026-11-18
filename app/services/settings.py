"""Key-value settings stored in the database. Keys: docs/03-data-model.md."""
from sqlalchemy.orm import Session

from ..models import Setting

DEFAULTS = {
    "public_base_url": "",
    "service_tel": "",
    "default_warranty_months": "12",
}


def get(db: Session, key: str) -> str:
    row = db.get(Setting, key)
    return row.value if row is not None else DEFAULTS.get(key, "")


def get_int(db: Session, key: str) -> int:
    try:
        return int(get(db, key))
    except ValueError:
        return int(DEFAULTS.get(key, "0") or 0)


def put(db: Session, key: str, value: str) -> None:
    row = db.get(Setting, key)
    if row is None:
        db.add(Setting(key=key, value=value))
    else:
        row.value = value
