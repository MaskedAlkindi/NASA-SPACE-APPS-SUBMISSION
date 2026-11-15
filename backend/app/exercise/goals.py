"""Pure goal, streak, and adherence math. No database access."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable


def period_bounds(period: str, today: date) -> tuple[date, date]:
    if period == "day":
        return today, today
    if period == "week":
        start = today - timedelta(days=today.weekday())
        return start, start + timedelta(days=6)
    if period == "month":
        start = today.replace(day=1)
        if start.month == 12:
            end = date(start.year + 1, 1, 1) - timedelta(days=1)
        else:
            end = date(start.year, start.month + 1, 1) - timedelta(days=1)
        return start, end
    if period == "year":
        return date(today.year, 1, 1), date(today.year, 12, 31)
    raise ValueError(f"unknown period '{period}'")


def completion_pct(actual: float, target: float) -> float:
    if target <= 0:
        return 0.0
    return round(min(100.0, (actual / target) * 100.0), 1)


def evaluate_goals(sessions: list[dict], goals: list[dict], today: date) -> list[dict]:
    """``sessions`` items need ``date`` (datetime.date), ``minutes`` (float), ``status``."""
    done = [s for s in sessions if s.get("status", "completed") == "completed" and s.get("date")]
    out = []
    for g in goals:
        start, end = period_bounds(g["period"], today)
        chosen = [s for s in done if start <= s["date"] <= end]
        if g["metric"] == "minutes":
            actual = round(sum(float(s.get("minutes") or 0) for s in chosen), 1)
        elif g["metric"] == "sessions":
            actual = float(len(chosen))
        else:
            raise ValueError(f"unknown goal metric '{g['metric']}'")
        target = float(g["target"])
        out.append({
            "period": g["period"], "metric": g["metric"], "label": g.get("label") or g["period"],
            "target": target, "actual": actual, "pct": completion_pct(actual, target),
            "start": start.isoformat(), "end": end.isoformat(),
            "example_only": bool(g.get("example_only", True)),
        })
    return out


def streak_days(session_dates: Iterable[date], today: date) -> int:
    days = set(session_dates)
    cursor = today if today in days else today - timedelta(days=1)
    if cursor not in days:
        return 0
    n = 0
    while cursor in days:
        n += 1
        cursor -= timedelta(days=1)
    return n


def missed_dates(session_dates: Iterable[date], scheduled_weekdays: Iterable[int],
                 start: date, end: date, today: date) -> list[str]:
    """Scheduled days before today with no completed session, inclusive of ``start``."""
    done = set(session_dates)
    weekdays = set(scheduled_weekdays)
    last = min(end, today - timedelta(days=1))
    missed = []
    cursor = start
    while cursor <= last:
        if cursor.weekday() in weekdays and cursor not in done:
            missed.append(cursor.isoformat())
        cursor += timedelta(days=1)
    return missed


def weekly_adherence(session_dates: Iterable[date], target_sessions: float, today: date, weeks: int = 8) -> list[dict]:
    done = set(session_dates)
    # Monday of the current week, then walk backwards.
    this_monday = today - timedelta(days=today.weekday())
    rows = []
    for i in range(weeks - 1, -1, -1):
        start = this_monday - timedelta(days=7 * i)
        count = sum(1 for offset in range(7) if (start + timedelta(days=offset)) in done)
        rows.append({
            "week_start": start.isoformat(),
            "sessions": count,
            "target": target_sessions,
            "pct": completion_pct(count, target_sessions),
        })
    return rows


def daily_series(sessions: list[dict], today: date, days: int = 30) -> list[dict]:
    start = today - timedelta(days=days - 1)
    bucket: dict[date, dict] = {}
    cursor = start
    while cursor <= today:
        bucket[cursor] = {"date": cursor.isoformat(), "minutes": 0.0, "sessions": 0}
        cursor += timedelta(days=1)
    for s in sessions:
        d = s.get("date")
        if d in bucket and s.get("status", "completed") == "completed":
            bucket[d]["minutes"] = round(bucket[d]["minutes"] + float(s.get("minutes") or 0), 1)
            bucket[d]["sessions"] += 1
    return list(bucket.values())
