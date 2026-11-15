"""Additive tables for the MQTT habitat bridge (created by create_all)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.models import Base, utcnow


class MqttBroker(Base):
    __tablename__ = "mqtt_broker"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)          # single row, id = 1
    host: Mapped[str] = mapped_column(String(255), default="mosquitto")
    port: Mapped[int] = mapped_column(Integer, default=1883)
    username: Mapped[str] = mapped_column(String(120), default="")
    password: Mapped[str] = mapped_column(Text, default="")
    tls: Mapped[bool] = mapped_column(Boolean, default=False)
    discover: Mapped[str] = mapped_column(String(255), default="habitat/#")   # topics shown as "seen" for assignment
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MqttMapping(Base):
    __tablename__ = "mqtt_mappings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    topic: Mapped[str] = mapped_column(String(255))                # exact topic or MQTT wildcard (+, #)
    metric: Mapped[str] = mapped_column(String(64))                # canonical metric (cabin_co2, ...)
    json_path: Mapped[str] = mapped_column(String(255), default="")   # "" = payload is a number; "data.co2" for JSON
    scale: Mapped[float] = mapped_column(Float, default=1.0)       # value = raw * scale + offset
    offset: Mapped[float] = mapped_column(Float, default=0.0)
    astronaut_id: Mapped[str | None] = mapped_column(String(32), nullable=True)   # for per-person sensors
    data_class: Mapped[str] = mapped_column(String(16), default="real")
    min_interval_s: Mapped[float] = mapped_column(Float, default=10.0)   # store at most one reading per interval
    label: Mapped[str] = mapped_column(String(120), default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str] = mapped_column(Text, default="")
