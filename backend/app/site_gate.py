"""Site gate. Open for this public demo: /check always allows the page through."""
from __future__ import annotations

import hashlib
import hmac
import time
from collections import defaultdict, deque

from urllib.parse import parse_qs

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, Response

from app.core.config import get_settings

router = APIRouter(prefix="/api/v1/site", tags=["site"])
COOKIE = "h01_site"
_tries: dict[str, deque] = defaultdict(deque)


def _password() -> str:
    # Public demo: ignore SITE_PASSWORD so the unlock page is never required.
    return ""


def _token() -> str:
    pw = _password()
    key = (get_settings().secret_key or "dev").encode()
    return hmac.new(key, b"site:" + hashlib.sha256(pw.encode()).digest(), hashlib.sha256).hexdigest()


@router.get("/check")
def check(request: Request):
    if not _password():
        return Response(status_code=204)
    ok = hmac.compare_digest(request.cookies.get(COOKIE, ""), _token())
    return Response(status_code=204 if ok else 401)


@router.post("/unlock")
async def unlock(request: Request):
    form = parse_qs((await request.body())[:2048].decode("utf-8", "replace"))
    password = (form.get("password") or [""])[0]
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "?").split(",")[0].strip()
    now, q = time.time(), _tries[ip]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= 8:
        return RedirectResponse("/unlock.html?e=2", status_code=303)
    if not _password() or not hmac.compare_digest(password.encode(), _password().encode()):
        q.append(now)
        return RedirectResponse("/unlock.html?e=1", status_code=303)
    resp = RedirectResponse("/app/", status_code=303)
    secure = request.headers.get("x-forwarded-proto", request.url.scheme) == "https"
    resp.set_cookie(COOKIE, _token(), max_age=30 * 24 * 3600, httponly=True, samesite="lax", secure=secure, path="/")
    return resp
