"""Turn raw measurements into one-row-per-day frames for models and summaries."""
from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Measurement
from app.schemas.metrics import METRICS

AGG = {"mean": "mean", "sum": "sum", "min": "min", "max": "max", "last": "last"}


def load_measurements(db: Session, astronaut_id: str | None, metrics: list[str] | None = None,
                      since: datetime | None = None, until: datetime | None = None) -> pd.DataFrame:
    q = select(Measurement.metric, Measurement.value, Measurement.timestamp, Measurement.data_class,
               Measurement.source_module)
    q = q.where(Measurement.astronaut_id.is_(None) if astronaut_id is None else Measurement.astronaut_id == astronaut_id)
    if metrics:
        q = q.where(Measurement.metric.in_(metrics))
    if since:
        q = q.where(Measurement.timestamp >= since)
    if until:
        q = q.where(Measurement.timestamp <= until)
    rows = db.execute(q.order_by(Measurement.timestamp)).all()
    df = pd.DataFrame(rows, columns=["metric", "value", "timestamp", "data_class", "source_module"])
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df


def daily_frame(raw: pd.DataFrame) -> pd.DataFrame:
    """Pivot raw measurements to daily rows using each metric's aggregation rule.

    resting_heart_rate falls back to the 5th percentile of heart_rate when no
    device-reported resting HR exists for that day.
    """
    if raw.empty:
        return pd.DataFrame(columns=["date"])
    raw = raw.dropna(subset=["value"]).copy()
    raw["date"] = raw["timestamp"].dt.date
    parts = []
    for metric, g in raw.groupby("metric"):
        mdef = METRICS.get(metric)
        if not mdef:
            continue
        s = g.groupby("date")["value"].agg(AGG[mdef.daily]).rename(metric)
        parts.append(s)
    if not parts:
        return pd.DataFrame(columns=["date"])
    df = pd.concat(parts, axis=1).sort_index()
    if "heart_rate" in raw["metric"].unique():
        hr5 = raw[raw["metric"] == "heart_rate"].groupby("date")["value"].quantile(0.05)
        if "resting_heart_rate" not in df.columns:
            df["resting_heart_rate"] = hr5
        else:
            df["resting_heart_rate"] = df["resting_heart_rate"].fillna(hr5)
    df = df.reset_index().rename(columns={"index": "date"})
    df["date"] = pd.to_datetime(df["date"])
    return df


def astronaut_daily(db: Session, astronaut_id: str, days: int = 60) -> pd.DataFrame:
    latest = latest_timestamp(db, astronaut_id)
    if latest is None:
        return pd.DataFrame(columns=["date"])
    raw = load_measurements(db, astronaut_id, since=latest - timedelta(days=days))
    return daily_frame(raw)


def latest_timestamp(db: Session, astronaut_id: str | None) -> datetime | None:
    q = select(Measurement.timestamp)
    q = q.where(Measurement.astronaut_id.is_(None) if astronaut_id is None else Measurement.astronaut_id == astronaut_id)
    return db.execute(q.order_by(Measurement.timestamp.desc()).limit(1)).scalar()
