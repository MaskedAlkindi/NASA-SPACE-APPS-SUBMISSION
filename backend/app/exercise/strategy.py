"""Chooses where a camera workout is counted.

Order is fixed: on-device pose, then an explicitly configured inference service
the user has consented to, then manual entry. Nothing here opens a camera or
sends an image.
"""
from __future__ import annotations


def choose_strategy(*, camera_permission: str, local_pose: str, remote_configured: bool,
                    remote_consent: bool, remote_status: str) -> dict[str, str]:
    """Return ``strategy`` of ``local``, ``remote``, or ``manual`` plus a reason.

    ``camera_permission``: granted | denied | prompt
    ``local_pose``: ready | failed | unavailable
    ``remote_status``: ready | failed | skipped
    """
    if camera_permission == "denied":
        return {"strategy": "manual", "reason": "Camera permission was denied. Log the workout manually."}
    if local_pose == "ready":
        return {"strategy": "local", "reason": "Pose detection is running in this browser. Video stays on the device."}
    if remote_configured and remote_consent and remote_status == "ready":
        return {"strategy": "remote",
                "reason": "Using the configured inference service. You consented to send frames or landmarks for this session."}
    if local_pose == "failed" and remote_configured and remote_consent and remote_status == "failed":
        return {"strategy": "manual", "reason": "On-device pose detection failed and the inference service did not respond. Log the workout manually."}
    if local_pose in {"failed", "unavailable"}:
        if remote_configured and not remote_consent:
            return {"strategy": "manual",
                    "reason": "On-device pose detection is unavailable. Remote processing stays off until you allow it. Log the workout manually or allow remote processing."}
        return {"strategy": "manual",
                "reason": "On-device pose detection is unavailable and no inference service is ready. Log the workout manually."}
    return {"strategy": "manual", "reason": "Camera tracking is not ready. Log the workout manually."}
