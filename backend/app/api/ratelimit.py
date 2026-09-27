"""Per-client request caps: fixed one-minute windows in process memory.

The free tier runs one API instance, so a shared store buys nothing yet.
Keyed on request.client.host; behind a proxy, uvicorn must be told to trust
X-Forwarded-For (FORWARDED_ALLOW_IPS, set in render.yaml) or every caller
shares the proxy's bucket.
"""

import threading
import time
from collections import Counter
from typing import Any

from fastapi import Depends, HTTPException, Request

WINDOW_SECONDS = 60


class Limiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._window = -1
        self._counts: Counter[tuple[str, str]] = Counter()

    def allow(self, scope: str, client: str, per_minute: int) -> bool:
        window = int(time.monotonic() // WINDOW_SECONDS)
        with self._lock:
            if window != self._window:
                self._window, self._counts = window, Counter()
            self._counts[scope, client] += 1
            return self._counts[scope, client] <= per_minute


def rate_limit(scope: str, per_minute: int) -> Any:
    def check(request: Request) -> None:
        client = request.client.host if request.client else "unknown"
        limiter: Limiter = request.app.state.limiter
        if not limiter.allow(scope, client, per_minute):
            raise HTTPException(
                status_code=429,
                detail="too many requests, retry in a minute",
                headers={"x-error-code": "RATE_LIMITED", "Retry-After": str(WINDOW_SECONDS)},
            )

    return Depends(check)
