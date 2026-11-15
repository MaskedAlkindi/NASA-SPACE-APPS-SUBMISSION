"""Desktop / local inference handlers.

The browser counts repetitions on-device. This module is the optional second
strategy: a process that accepts pose landmarks, or a single frame only when
the caller sets ``consent`` to ``explicit_frame_upload`` and the server allows
frames. Frames are not stored.
"""
from __future__ import annotations

from typing import Any

from app.exercise.tracking import TRACKED_EXERCISES, RepCounter


class InferenceError(Exception):
    def __init__(self, code: str, message: str, status: int):
        super().__init__(message)
        self.code = code
        self.status = status


def mediapipe_status() -> dict[str, Any]:
    try:
        import mediapipe  # type: ignore  # noqa: F401
        return {"installed": True}
    except Exception as exc:
        return {"installed": False, "detail": str(exc).splitlines()[0]}


def handle_landmarks(payload: dict) -> dict[str, Any]:
    consent = payload.get("consent")
    if consent not in {"landmarks_only", "explicit_frame_upload"}:
        raise InferenceError("consent_required", "Send consent='landmarks_only' before remote landmark processing.", 403)
    exercise_id = payload.get("exercise_id")
    if exercise_id not in TRACKED_EXERCISES:
        raise InferenceError("unknown_exercise", f"Camera tracking supports {', '.join(TRACKED_EXERCISES)}.", 422)
    frames = payload.get("frames")
    if frames is None and payload.get("landmarks") is not None:
        frames = [{"t_ms": payload.get("t_ms", 0), "landmarks": payload.get("landmarks")}]
    if not isinstance(frames, list) or not frames:
        raise InferenceError("no_frames", "Provide landmarks or a frames list.", 422)
    if len(frames) > 5000:
        raise InferenceError("too_many_frames", "Send at most 5000 frames per call.", 422)
    counter = RepCounter.from_state(exercise_id, payload.get("state") if isinstance(payload.get("state"), dict) else None)
    snap = counter.snapshot("ready")
    for fr in frames:
        if not isinstance(fr, dict):
            raise InferenceError("bad_frame", "Each frame must be an object.", 422)
        snap = counter.update(fr.get("landmarks"), int(fr.get("t_ms") or 0))
    return {"engine": "rules:pose-counter-1.0.0", "snapshot": snap, "state": counter.export_state(),
            "stored_video": False}


# Optional hook: fn(image_bytes) -> landmark dict. Unset until a pose runtime is registered.
FRAME_DECODER = None


def handle_frame(payload: dict, *, allow_frames: bool) -> dict[str, Any]:
    """Accept a frame only with explicit consent. Never stores the image."""
    if payload.get("consent") != "explicit_frame_upload":
        raise InferenceError("consent_required",
                             "Camera frames are processed only when consent is 'explicit_frame_upload'.", 403)
    if not allow_frames:
        raise InferenceError("frames_disabled", "This service is not configured to accept camera frames.", 403)
    image = payload.get("image_base64")
    if not image:
        raise InferenceError("no_image", "No frame was attached.", 422)
    if FRAME_DECODER is None:
        if not mediapipe_status()["installed"]:
            raise InferenceError(
                "pose_runtime_missing",
                "No frame decoder is registered and MediaPipe is not installed here. Count reps in the browser, send landmarks, or log the workout manually.",
                503)
        raise InferenceError(
            "decoder_not_registered",
            "MediaPipe is installed but no frame decoder is registered. Send landmarks to the landmarks endpoint. The frame was not stored.",
            501)
    import base64
    try:
        raw = base64.b64decode(image, validate=True)
    except Exception as exc:
        raise InferenceError("bad_image", "The frame could not be decoded.", 422) from exc
    if len(raw) > 1_500_000:
        raise InferenceError("image_too_large", "Frames must be under 1.5 MB.", 413)
    landmarks = FRAME_DECODER(raw)
    return handle_landmarks({
        "consent": "landmarks_only",
        "exercise_id": payload.get("exercise_id"),
        "t_ms": payload.get("t_ms", 0),
        "landmarks": landmarks,
        "state": payload.get("state"),
    })
