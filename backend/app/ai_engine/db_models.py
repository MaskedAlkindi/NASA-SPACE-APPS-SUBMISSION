"""Additive tables for the AI engine (created by the existing create_all; no existing table is changed)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.models import Base, utcnow


class AiModelState(Base):
    __tablename__ = "ai_model_state"
    model_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    state: Mapped[dict] = mapped_column(JSON, default=dict)          # {"enabled": bool, "thresholds": {...}}
    updated_by: Mapped[str] = mapped_column(String(64), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AiAssessment(Base):
    __tablename__ = "ai_assessments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    astronaut_id: Mapped[str] = mapped_column(String(32))
    model_id: Mapped[str] = mapped_column(String(64))
    model_version: Mapped[str] = mapped_column(String(32))
    assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    status: Mapped[str] = mapped_column(String(24))
    category: Mapped[str] = mapped_column(String(32))
    severity: Mapped[str] = mapped_column(String(16))
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)         # full Assessment (ai_assessment.v1)

    __table_args__ = (Index("ix_ai_assess_astro_model_time", "astronaut_id", "model_id", "assessed_at"),)


class AiExerciseSession(Base):
    """Exercise session summaries received through the exercise_session_summary.v1 contract."""
    __tablename__ = "ai_exercise_sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    astronaut_id: Mapped[str] = mapped_column(String(32), index=True)
    session_id: Mapped[str] = mapped_column(String(80))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    planned: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (UniqueConstraint("astronaut_id", "session_id", name="uq_ai_exercise_session"),)
