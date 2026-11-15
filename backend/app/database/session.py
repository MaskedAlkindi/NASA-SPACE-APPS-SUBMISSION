from __future__ import annotations

import logging
import time
from collections.abc import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.database.models import Base

log = logging.getLogger("hmt.db")
_settings = get_settings()

_kwargs = {"pool_pre_ping": True}
if _settings.database_url.startswith("sqlite"):
    _kwargs["connect_args"] = {"check_same_thread": False}
engine = create_engine(_settings.database_url, **_kwargs)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def wait_for_db(retries: int = 30, delay: float = 2.0) -> None:
    for i in range(retries):
        try:
            with engine.connect() as c:
                c.execute(text("SELECT 1"))
            return
        except Exception as e:  # pragma: no cover - startup race only
            log.warning("database not ready (%s/%s): %s", i + 1, retries, e)
            time.sleep(delay)
    raise RuntimeError("database unavailable")


def init_db() -> None:
    """Create tables (idempotent). Schema is small and additive, so create_all acts as our migration."""
    Base.metadata.create_all(engine)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
