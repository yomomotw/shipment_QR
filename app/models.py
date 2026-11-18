"""Tables for phase 1. See docs/03-data-model.md."""
from datetime import date

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base, TimestampMixin

ROLES = ("manager", "agent", "engineer")
ROLE_LABELS = {"manager": "負責人", "agent": "客服", "engineer": "工程師"}


class User(Base, TimestampMixin):
    __tablename__ = "user"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(default=True)


class Setting(Base, TimestampMixin):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


class Batch(Base, TimestampMixin):
    __tablename__ = "batch"
    id: Mapped[int] = mapped_column(primary_key=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("user.id"))
    label_size: Mapped[str] = mapped_column(String(16), default="60x40")
    note: Mapped[str] = mapped_column(Text, default="")
    devices: Mapped[list["Device"]] = relationship(back_populates="batch", order_by="Device.id")


class Device(Base, TimestampMixin):
    __tablename__ = "device"
    id: Mapped[int] = mapped_column(primary_key=True)
    serial: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    scan_code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    model: Mapped[str] = mapped_column(String(200))
    spec: Mapped[str] = mapped_column(Text, default="")
    ship_date: Mapped[date]
    cust_po: Mapped[str] = mapped_column(String(120), index=True)
    int_po: Mapped[str] = mapped_column(String(120), index=True)
    customer_name: Mapped[str] = mapped_column(String(200), default="", index=True)
    warranty_months: Mapped[int]
    warranty_start: Mapped[date]
    warranty_end: Mapped[date]
    # Service phone printed on the label, frozen at creation so reprints match the QR.
    service_tel: Mapped[str] = mapped_column(String(60))
    qr_fields: Mapped[list] = mapped_column(JSON, default=list)
    # Exact QR text at generation time. Never rewritten except by explicit regenerate.
    qr_payload: Mapped[str] = mapped_column(Text)
    external_ref: Mapped[str | None] = mapped_column(String(120), default=None)
    note: Mapped[str] = mapped_column(Text, default="")
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("batch.id"))
    batch: Mapped[Batch | None] = relationship(back_populates="devices")
