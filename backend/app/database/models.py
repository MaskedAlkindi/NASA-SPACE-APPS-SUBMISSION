from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import (JSON, Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text,
                        UniqueConstraint)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Mission(Base):
    __tablename__ = "missions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    start_date: Mapped[date] = mapped_column(Date)
    planned_duration_days: Mapped[int] = mapped_column(Integer)
    vehicle: Mapped[str] = mapped_column(String(120), default="")
    data_class: Mapped[str] = mapped_column(String(16), default="simulated")


class Astronaut(Base):
    __tablename__ = "astronauts"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    callsign: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(120))
    mission_id: Mapped[str] = mapped_column(ForeignKey("missions.id"))
    data_class: Mapped[str] = mapped_column(String(16), default="simulated")


class User(Base):
    __tablename__ = "users"
    username: Mapped[str] = mapped_column(String(64), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(32))
    astronaut_id: Mapped[str | None] = mapped_column(ForeignKey("astronauts.id"), nullable=True)
    passcode_hash: Mapped[str] = mapped_column(String(200))


class Measurement(Base):
    __tablename__ = "measurements"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    astronaut_id: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    metric: Mapped[str] = mapped_column(String(48))
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    value_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    unit: Mapped[str] = mapped_column(String(24))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source_device: Mapped[str] = mapped_column(String(120), default="unknown")
    source_module: Mapped[str] = mapped_column(String(64))
    quality: Mapped[str] = mapped_column(String(16), default="unknown")
    data_class: Mapped[str] = mapped_column(String(16), default="real")
    external_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        Index("ix_meas_astro_metric_ts", "astronaut_id", "metric", "timestamp"),
        UniqueConstraint("source_module", "astronaut_id", "external_id", name="uq_meas_external"),
    )


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    astronaut_id: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    severity: Mapped[str] = mapped_column(String(16))         # info | caution | warning
    category: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text)
    evidence: Mapped[list] = mapped_column(JSON, default=list)   # triggering measurements
    recommendation: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(64))            # rule id or model version
    dedupe_key: Mapped[str] = mapped_column(String(160), index=True)
    data_class: Mapped[str] = mapped_column(String(16), default="simulated")
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)


class ResearchDataset(Base):
    __tablename__ = "research_datasets"
    accession: Mapped[str] = mapped_column(String(32), primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, default="")
    organism: Mapped[str] = mapped_column(Text, default="")
    mission: Mapped[str] = mapped_column(Text, default="")
    project_type: Mapped[str] = mapped_column(Text, default="")
    assay_types: Mapped[str] = mapped_column(Text, default="")
    release_date: Mapped[str] = mapped_column(Text, default="")
    source_url: Mapped[str] = mapped_column(Text)
    license: Mapped[str] = mapped_column(Text)
    doi: Mapped[str] = mapped_column(Text, default="")
    citation: Mapped[str] = mapped_column(Text, default="")
    relevance: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="metadata_only")  # metadata_only|downloaded|restricted|error
    files: Mapped[list] = mapped_column(JSON, default=list)
    extra: Mapped[dict] = mapped_column(JSON, default=dict)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ResearchObservation(Base):
    """Rows parsed from downloaded NASA data files (real research data, NOT our crew)."""
    __tablename__ = "research_observations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    accession: Mapped[str] = mapped_column(ForeignKey("research_datasets.accession"), index=True)
    source_file: Mapped[str] = mapped_column(String(300))
    subject_id: Mapped[str] = mapped_column(String(32))
    analyte: Mapped[str] = mapped_column(String(160))
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str] = mapped_column(String(48), default="")
    range_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    range_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    timepoint: Mapped[str] = mapped_column(String(32))
    phase: Mapped[str] = mapped_column(String(16))    # preflight | postflight | inflight | unknown


class ResearchFinding(Base):
    __tablename__ = "research_findings"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    topic: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(300))
    summary: Mapped[str] = mapped_column(Text)
    evidence_type: Mapped[str] = mapped_column(String(64))   # computed_from_dataset | curated_summary
    source_accession: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_url: Mapped[str] = mapped_column(Text, default="")
    caveats: Mapped[str] = mapped_column(Text, default="")
    stats: Mapped[dict] = mapped_column(JSON, default=dict)


class AppSetting(Base):
    """Small key/value store for runtime settings changed from the UI (e.g. assistant provider)."""
    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_by: Mapped[str] = mapped_column(String(64), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AssistantUsage(Base):
    __tablename__ = "assistant_usage"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), index=True)
    day: Mapped[date] = mapped_column(Date, index=True)
    mode: Mapped[str] = mapped_column(String(16))      # openai | offline
    model: Mapped[str] = mapped_column(String(64), default="")
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ExerciseProfile(Base):
    """Per-astronaut exercise preferences. Example data, not a medical record."""
    __tablename__ = "exercise_profiles"
    astronaut_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    fitness_level: Mapped[str] = mapped_column(String(32), default="intermediate")
    focus: Mapped[str] = mapped_column(String(32), default="balanced")
    limitations: Mapped[str] = mapped_column(Text, default="")
    equipment: Mapped[list] = mapped_column(JSON, default=list)
    mission_phase: Mapped[str] = mapped_column(String(64), default="in_flight")
    notes: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ExerciseAssignment(Base):
    __tablename__ = "exercise_assignments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    astronaut_id: Mapped[str] = mapped_column(String(32), index=True)
    program_id: Mapped[str] = mapped_column(String(80))
    kind: Mapped[str] = mapped_column(String(32))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    program_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WorkoutSession(Base):
    __tablename__ = "workout_sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    astronaut_id: Mapped[str] = mapped_column(String(32), index=True)
    program_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    source: Mapped[str] = mapped_column(String(16), default="manual")
    status: Mapped[str] = mapped_column(String(16), default="completed")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exercises: Mapped[list] = mapped_column(JSON, default=list)
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    perceived_exertion: Mapped[int | None] = mapped_column(Integer, nullable=True)
    heart_rate_avg: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    data_class: Mapped[str] = mapped_column(String(16), default="real")
    client_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    sync_health: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        UniqueConstraint("astronaut_id", "client_id", name="uq_workout_client"),
    )


class ExerciseGoal(Base):
    __tablename__ = "exercise_goals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    astronaut_id: Mapped[str] = mapped_column(String(32), index=True)
    period: Mapped[str] = mapped_column(String(16))
    metric: Mapped[str] = mapped_column(String(24))
    target: Mapped[float] = mapped_column(Float)
    label: Mapped[str] = mapped_column(String(120))
    example_only: Mapped[bool] = mapped_column(Boolean, default=True)
