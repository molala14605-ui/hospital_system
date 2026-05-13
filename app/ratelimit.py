"""Simple in-memory rate limiting per client IP (no Redis required)."""

import threading
import time
from collections import defaultdict

from fastapi import HTTPException, Request, status

_lock = threading.Lock()
_events: dict[tuple[str, str], list[float]] = defaultdict(list)


def _hit(route_key: str, request: Request, limit: int, window_seconds: int = 60) -> None:
    ip = request.client.host if request.client else "unknown"
    k = (ip, route_key)
    now = time.time()
    with _lock:
        lst = _events[k]
        lst[:] = [t for t in lst if now - t < window_seconds]
        if len(lst) >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please wait a minute and try again.",
            )
        lst.append(now)


def check_login_rate(request: Request) -> None:
    _hit("auth_login", request, 30, 60)


def check_register_rate(request: Request) -> None:
    _hit("auth_register", request, 20, 60)


def check_token_rate(request: Request) -> None:
    _hit("auth_token", request, 30, 60)
