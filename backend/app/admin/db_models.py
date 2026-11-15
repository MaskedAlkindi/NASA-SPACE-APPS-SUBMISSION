"""Tables for Mission Control administration."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.models import Base, utcnow


class ExtraPasscode(Base):
    """Additional passcodes that sign in as the Mission Control account (e.g. one per demo guest)."""
    __tablename__ = "mc_extra_passcodes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    label: Mapped[str] = mapped_column(String(80))
    passcode_hash: Mapped[str] = mapped_column(String(200))
    created_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_used: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
