"""Meal rows and a daily body-mass note. Separate from the measurement stream."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.models import Base, utcnow


class MealLog(Base):
    __tablename__ = "meal_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    astronaut_id: Mapped[str] = mapped_column(String(32), index=True)
    eaten_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    name: Mapped[str] = mapped_column(String(160))
    meal: Mapped[str] = mapped_column(String(16), default="snack")
    kcal: Mapped[float] = mapped_column(Float, default=0)
    protein_g: Mapped[float] = mapped_column(Float, default=0)
    carb_g: Mapped[float] = mapped_column(Float, default=0)
    fat_g: Mapped[float] = mapped_column(Float, default=0)
    fluid_ml: Mapped[float] = mapped_column(Float, default=0)
    sodium_mg: Mapped[float] = mapped_column(Float, default=0)
    calcium_mg: Mapped[float] = mapped_column(Float, default=0)
    iron_mg: Mapped[float] = mapped_column(Float, default=0)
    vitamin_d_iu: Mapped[float] = mapped_column(Float, default=0)
    notes: Mapped[str] = mapped_column(Text, default="")
    data_class: Mapped[str] = mapped_column(String(16), default="real")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MassLog(Base):
    __tablename__ = "mass_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    astronaut_id: Mapped[str] = mapped_column(String(32), index=True)
    logged_on: Mapped[date] = mapped_column(Date, index=True)
    kg: Mapped[float] = mapped_column(Float)
    note: Mapped[str] = mapped_column(Text, default="")
    data_class: Mapped[str] = mapped_column(String(16), default="real")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (UniqueConstraint("astronaut_id", "logged_on", name="uq_mass_day"),)
