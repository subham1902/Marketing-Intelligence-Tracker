"""Public-site protections: owner-only actions and per-IP rate limits.

Both are no-ops unless ``COMPETE_PUBLIC_MODE`` is true, so local use stays
unrestricted. On the hosted VM the API is only reachable through Caddy, so the
first ``X-Forwarded-For`` entry is the real visitor IP.
"""

from __future__ import annotations

import hmac
import os
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import HTTPException, Request

_TRUE = {"1", "true", "yes", "on"}


def public_mode() -> bool:
    return os.environ.get("COMPETE_PUBLIC_MODE", "").strip().lower() in _TRUE


def require_admin(request: Request) -> None:
    """Owner-only actions (server AI key, companies, pipeline). Needs X-Admin-Token in public mode."""
    if not public_mode():
        return
    expected = os.environ.get("COMPETE_ADMIN_TOKEN", "").strip()
    given = request.headers.get("x-admin-token", "").strip()
    if not expected or expected == "change-me" or not hmac.compare_digest(given, expected):
        raise HTTPException(status_code=403, detail="This setting is managed by the site owner.")


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


_HITS: dict[tuple[str, str], deque[float]] = defaultdict(deque)
_LOCK = threading.Lock()


def reset() -> None:
    with _LOCK:
        _HITS.clear()


def rate_limit(bucket: str, limit: int, window_seconds: float) -> Callable[[Request], None]:
    """Dependency: at most ``limit`` requests per IP per window for this bucket (public mode only)."""

    def dep(request: Request) -> None:
        if not public_mode():
            return
        key = (bucket, client_ip(request))
        now = time.monotonic()
        with _LOCK:
            q = _HITS[key]
            while q and now - q[0] > window_seconds:
                q.popleft()
            if len(q) >= limit:
                wait = int(window_seconds - (now - q[0])) + 1
                raise HTTPException(
                    status_code=429,
                    detail=f"You're going a bit fast. Please try again in about {max(wait, 1)} seconds.",
                )
            q.append(now)

    return dep


run_limit = rate_limit("runs", 6, 600)        # research, refresh and marketing runs
chat_limit = rate_limit("chat", 30, 60)       # guide assistant
