"""Optional desktop inference service.

Run it on the machine that should see landmarks or, only when configured, frames:

    set INFERENCE_TOKEN=choose-a-long-token
    set EXERCISE_ALLOW_REMOTE_FRAMES=false
    python services/pose_inference/server.py

Then point the API at it with EXERCISE_INFERENCE_URL=http://127.0.0.1:8090 and
the same EXERCISE_INFERENCE_TOKEN. Bind stays on 127.0.0.1 unless INFERENCE_HOST
is set. Put TLS in front before exposing it beyond the machine.

The service does not store images. /v1/landmarks counts reps from pose
landmarks. /v1/frame rejects the body unless consent is explicit_frame_upload
and EXERCISE_ALLOW_REMOTE_FRAMES=true.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]

from fastapi import FastAPI, Header, HTTPException  # noqa: E402

from app.exercise.inference_api import InferenceError, handle_frame, handle_landmarks, mediapipe_status  # noqa: E402

app = FastAPI(title="Exercise pose inference", version="1.0.0",
              description="Landmark rep counting for the HEALTH-01. Does not store camera video.")


def _auth(authorization: str | None) -> None:
    token = os.environ.get("INFERENCE_TOKEN", "")
    if not token:
        raise HTTPException(503, "Set INFERENCE_TOKEN before accepting requests.")
    if authorization != f"Bearer {token}":
        raise HTTPException(401, "Unauthorized", headers={"WWW-Authenticate": "Bearer"})


def _run(fn):
    try:
        return fn()
    except InferenceError as exc:
        raise HTTPException(exc.status, {"code": exc.code, "detail": str(exc)}) from None


@app.get("/health")
def health():
    return {"status": "ok", "mediapipe": mediapipe_status(), "stores_video": False}


@app.post("/v1/landmarks")
def landmarks(payload: dict, authorization: str | None = Header(default=None)):
    _auth(authorization)
    return _run(lambda: handle_landmarks(payload))


@app.post("/v1/frame")
def frame(payload: dict, authorization: str | None = Header(default=None)):
    _auth(authorization)
    allow = os.environ.get("EXERCISE_ALLOW_REMOTE_FRAMES", "false").lower() in {"1", "true", "yes"}
    return _run(lambda: handle_frame(payload, allow_frames=allow))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=os.environ.get("INFERENCE_HOST", "127.0.0.1"),
                port=int(os.environ.get("INFERENCE_PORT", "8090")))
