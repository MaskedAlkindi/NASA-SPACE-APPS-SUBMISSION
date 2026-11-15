"""Food log API. One crew member, one station day (UTC)."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import Principal, current_user, require_access
from app.database.models import Astronaut
from app.database.session import get_db
from app.nutrition.catalog import DISCLAIMER, FACTS, FOODS, MARKS, NUTRIENTS
from app.nutrition.models import MassLog, MealLog

router = APIRouter(prefix="/api/v1/nutrition", tags=["nutrition"])

MEALS = {"breakfast", "lunch", "dinner", "snack", "drink"}


class MealIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=160)
    meal: str = "snack"
    eaten_at: datetime | None = None
    kcal: float = Field(0, ge=0, le=5000)
    protein_g: float = Field(0, ge=0, le=400)
    carb_g: float = Field(0, ge=0, le=800)
    fat_g: float = Field(0, ge=0, le=400)
    fluid_ml: float = Field(0, ge=0, le=5000)
    sodium_mg: float = Field(0, ge=0, le=20000)
    calcium_mg: float = Field(0, ge=0, le=5000)
    iron_mg: float = Field(0, ge=0, le=200)
    vitamin_d_iu: float = Field(0, ge=0, le=20000)
    notes: str = Field("", max_length=500)


class MassIn(BaseModel):
    kg: float = Field(..., gt=20, lt=250)
    logged_on: date | None = None
    note: str = Field("", max_length=300)


def _day(value: str | None) -> date:
    if not value:
        return datetime.now(timezone.utc).date()
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(400, "Date must be YYYY-MM-DD") from None


def _bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    return start, start + timedelta(days=1)


def _crew(db: Session, astronaut_id: str, user: Principal) -> None:
    require_access(astronaut_id, user)
    if db.get(Astronaut, astronaut_id) is None:
        raise HTTPException(404, "Astronaut not found")


def _meal_out(row: MealLog) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "meal": row.meal,
        "eaten_at": row.eaten_at.isoformat() if row.eaten_at else None,
        "notes": row.notes,
        "data_class": row.data_class,
        **{k: getattr(row, k) for k in NUTRIENTS},
    }


def _totals(rows: list[MealLog]) -> dict[str, float]:
    return {k: round(sum(getattr(r, k) or 0 for r in rows), 1) for k in NUTRIENTS}


@router.get("/foods")
def foods(_: Principal = Depends(current_user)):
    return {"foods": FOODS, "disclaimer": "Example portions for the demo, not a flight-menu analysis."}


@router.get("/astronauts/{astronaut_id}/day")
def day(astronaut_id: str, on: str | None = None, db: Session = Depends(get_db), user: Principal = Depends(current_user)):
    _crew(db, astronaut_id, user)
    when = _day(on)
    start, end = _bounds(when)
    rows = db.scalars(
        select(MealLog).where(MealLog.astronaut_id == astronaut_id, MealLog.eaten_at >= start, MealLog.eaten_at < end)
        .order_by(MealLog.eaten_at)
    ).all()
    mass = db.scalar(select(MassLog).where(MassLog.astronaut_id == astronaut_id, MassLog.logged_on == when))
    latest = db.scalars(
        select(MassLog).where(MassLog.astronaut_id == astronaut_id).order_by(MassLog.logged_on.desc()).limit(1)
    ).first()
    return {
        "date": when.isoformat(),
        "astronaut_id": astronaut_id,
        "disclaimer": DISCLAIMER,
        "marks": MARKS,
        "facts": FACTS,
        "totals": _totals(rows),
        "meals": [_meal_out(r) for r in rows],
        "mass": None if mass is None else {"kg": mass.kg, "logged_on": mass.logged_on.isoformat(), "note": mass.note, "data_class": mass.data_class},
        "latest_mass": None if latest is None else {"kg": latest.kg, "logged_on": latest.logged_on.isoformat(), "data_class": latest.data_class},
    }


@router.get("/astronauts/{astronaut_id}/history")
def history(astronaut_id: str, days: int = 14, db: Session = Depends(get_db), user: Principal = Depends(current_user)):
    _crew(db, astronaut_id, user)
    days = max(1, min(days, 60))
    end = datetime.now(timezone.utc).date()
    start_day = end - timedelta(days=days - 1)
    start, _ = _bounds(start_day)
    _, finish = _bounds(end)
    rows = db.scalars(
        select(MealLog).where(MealLog.astronaut_id == astronaut_id, MealLog.eaten_at >= start, MealLog.eaten_at < finish)
    ).all()
    by_day: dict[str, list[MealLog]] = {}
    for row in rows:
        stamp = row.eaten_at
        key = (stamp.astimezone(timezone.utc) if stamp.tzinfo else stamp).date().isoformat()
        by_day.setdefault(key, []).append(row)
    series = []
    cursor = start_day
    while cursor <= end:
        key = cursor.isoformat()
        totals = _totals(by_day.get(key, []))
        series.append({"date": key, **totals})
        cursor += timedelta(days=1)
    masses = db.scalars(
        select(MassLog).where(MassLog.astronaut_id == astronaut_id, MassLog.logged_on >= start_day, MassLog.logged_on <= end)
        .order_by(MassLog.logged_on)
    ).all()
    return {
        "days": series,
        "mass": [{"date": m.logged_on.isoformat(), "kg": m.kg, "data_class": m.data_class} for m in masses],
    }


@router.post("/astronauts/{astronaut_id}/meals")
def add_meal(astronaut_id: str, body: MealIn, db: Session = Depends(get_db), user: Principal = Depends(current_user)):
    _crew(db, astronaut_id, user)
    if body.meal not in MEALS:
        raise HTTPException(400, "Meal must be breakfast, lunch, dinner, snack or drink")
    eaten = body.eaten_at or datetime.now(timezone.utc)
    if eaten.tzinfo is None:
        eaten = eaten.replace(tzinfo=timezone.utc)
    row = MealLog(
        astronaut_id=astronaut_id, eaten_at=eaten, name=body.name.strip(), meal=body.meal,
        notes=body.notes.strip(), data_class="real",
        **{k: getattr(body, k) for k in NUTRIENTS},
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _meal_out(row)


@router.delete("/astronauts/{astronaut_id}/meals/{meal_id}")
def delete_meal(astronaut_id: str, meal_id: int, db: Session = Depends(get_db), user: Principal = Depends(current_user)):
    _crew(db, astronaut_id, user)
    row = db.get(MealLog, meal_id)
    if row is None or row.astronaut_id != astronaut_id:
        raise HTTPException(404, "Meal not found")
    db.delete(row)
    db.commit()
    return {"ok": True}


@router.put("/astronauts/{astronaut_id}/mass")
def save_mass(astronaut_id: str, body: MassIn, db: Session = Depends(get_db), user: Principal = Depends(current_user)):
    _crew(db, astronaut_id, user)
    when = body.logged_on or datetime.now(timezone.utc).date()
    row = db.scalar(select(MassLog).where(MassLog.astronaut_id == astronaut_id, MassLog.logged_on == when))
    if row is None:
        row = MassLog(astronaut_id=astronaut_id, logged_on=when, kg=body.kg, note=body.note.strip(), data_class="real")
        db.add(row)
    else:
        row.kg = body.kg
        row.note = body.note.strip()
        row.data_class = "real"
    db.commit()
    return {"kg": row.kg, "logged_on": row.logged_on.isoformat(), "note": row.note, "data_class": row.data_class}
