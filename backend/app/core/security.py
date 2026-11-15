"""Minimal, dependency-free auth: PBKDF2 passcodes + HMAC-signed bearer tokens.

Roles:
  astronaut       - may read/write only their own astronaut record
  flight_surgeon  - may read all crew data
  mission_control - may read all crew data and run the simulator / environment feeds
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings

CREW_WIDE_ROLES = {"flight_surgeon", "mission_control"}
bearer = HTTPBearer(auto_error=False)


def hash_passcode(passcode: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(8)
    digest = hashlib.pbkdf2_hmac("sha256", passcode.encode(), salt.encode(), 120_000).hex()
    return f"{salt}${digest}"


def verify_passcode(passcode: str, stored: str) -> bool:
    salt, _ = stored.split("$", 1)
    return hmac.compare_digest(hash_passcode(passcode, salt), stored)


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def create_token(username: str, role: str, astronaut_id: str | None) -> str:
    s = get_settings()
    payload = {"sub": username, "role": role, "aid": astronaut_id,
               "exp": int(time.time()) + s.token_ttl_hours * 3600}
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    sig = _b64(hmac.new(s.secret_key.encode(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"


@dataclass
class Principal:
    username: str
    role: str
    astronaut_id: str | None

    @property
    def crew_wide(self) -> bool:
        return self.role in CREW_WIDE_ROLES

    def can_access(self, astronaut_id: str | None) -> bool:
        if self.crew_wide:
            return True
        return astronaut_id is not None and astronaut_id == self.astronaut_id


def decode_token(token: str) -> Principal | None:
    try:
        body, sig = token.split(".", 1)
        expected = _b64(hmac.new(get_settings().secret_key.encode(), body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(_unb64(body))
        if payload["exp"] < time.time():
            return None
        return Principal(payload["sub"], payload["role"], payload.get("aid"))
    except Exception:
        return None


def current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> Principal:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token",
                            headers={"WWW-Authenticate": "Bearer"})
    p = decode_token(creds.credentials)
    if p is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token",
                            headers={"WWW-Authenticate": "Bearer"})
    return p


def require_access(astronaut_id: str, user: Principal) -> None:
    if not user.can_access(astronaut_id):
        # 404 rather than 403 so that astronaut IDs are not enumerable by other crew.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Astronaut not found")


def require_crew_wide(user: Principal = Depends(current_user)) -> Principal:
    if not user.crew_wide:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Mission control / flight surgeon role required")
    return user
