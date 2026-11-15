"""Additive tables for phone enrolment and server connections (created by create_all)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.models import Base, utcnow


class Device(Base):
    __tablename__ = "devices"
    device_uuid: Mapped[str] = mapped_column(String(36), primary_key=True)     # generated on the phone, shown in its app
    platform: Mapped[str] = mapped_column(String(16))                         # ios | android | other
    model: Mapped[str] = mapped_column(String(120), default="")
    app_version: Mapped[str] = mapped_column(String(32), default="")
    label: Mapped[str] = mapped_column(String(120), default="")               # operator's name for it
    astronaut_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")        # pending | assigned | revoked
    token_hash: Mapped[str] = mapped_column(String(64))                       # sha256 of the device secret
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_upload: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    uploads: Mapped[int] = mapped_column(Integer, default=0)
    assigned_by: Mapped[str] = mapped_column(String(64), default="")


class ServerConnection(Base):
    __tablename__ = "server_connections"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(32))                 # connector id from servers/connectors
    url: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    settings: Mapped[dict] = mapped_column(JSON, default=dict)     # connector-specific, never shown with secrets
    last_checked: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_status: Mapped[str] = mapped_column(String(16), default="unknown")   # ok | error | unknown
    last_message: Mapped[str] = mapped_column(Text, default="")
    last_data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
