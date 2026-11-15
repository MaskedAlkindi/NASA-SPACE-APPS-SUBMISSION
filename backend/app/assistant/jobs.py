"""Chat jobs that outlive the HTTP request.

The model can take a while. The page only starts the job and then polls.
Closing the assistant, or opening another page, does not stop the thread.
"""
from __future__ import annotations

import logging
import re
import threading
import uuid

from app.assistant import service as assistant
from app.database.session import SessionLocal

log = logging.getLogger("hmt.assistant.jobs")

_ID = re.compile(r"^[a-f0-9]{32}$")
_MAX = 100
_lock = threading.Lock()
_jobs: dict[str, dict] = {}


def _prune() -> None:
    if len(_jobs) < _MAX:
        return
    for key, job in list(_jobs.items()):
        if job["status"] != "pending":
            del _jobs[key]
        if len(_jobs) < _MAX:
            return


def start_chat_job(username: str, astronaut_id: str, message: str, history: list[dict],
                   provider: str | None, model: str | None, job_id: str | None = None) -> str:
    if not job_id or not _ID.match(job_id):
        job_id = uuid.uuid4().hex
    with _lock:
        existing = _jobs.get(job_id)
        if existing is not None:
            if existing["username"] == username:
                return job_id
            job_id = uuid.uuid4().hex
        _prune()
        job: dict = {"id": job_id, "username": username, "status": "pending", "result": None, "error": None}
        _jobs[job_id] = job

    def run() -> None:
        db = SessionLocal()
        try:
            result = assistant.chat(db, username, astronaut_id, message, history, provider, model)
            with _lock:
                job["status"] = "done"
                job["result"] = result
        except Exception as exc:  # the page is polling; it needs the failure as data, not a dead connection
            log.exception("chat job failed")
            with _lock:
                job["status"] = "error"
                job["error"] = str(exc) or "the model did not answer"
        finally:
            db.close()

    threading.Thread(target=run, name=f"chat-{job_id[:8]}", daemon=True).start()
    return job_id


def get_job(job_id: str, username: str) -> dict | None:
    with _lock:
        job = _jobs.get(job_id)
        if job is None or job["username"] != username:
            return None
        return {
            "id": job["id"],
            "username": job["username"],
            "status": job["status"],
            "result": job["result"],
            "error": job["error"],
        }
