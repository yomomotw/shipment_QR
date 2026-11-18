from datetime import datetime, timezone

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from . import config


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


_engine = None
SessionLocal = sessionmaker(autoflush=False, expire_on_commit=False)


def db_url() -> str:
    return f"sqlite:///{config.data_dir() / 'app.db'}"


def init_engine():
    """(Re)create the engine from current config. Called at app startup and by tests."""
    global _engine
    if _engine is not None:
        _engine.dispose()
    _engine = create_engine(db_url(), connect_args={"check_same_thread": False})

    @event.listens_for(_engine, "connect")
    def _fk_on(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    SessionLocal.configure(bind=_engine)
    return _engine


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
