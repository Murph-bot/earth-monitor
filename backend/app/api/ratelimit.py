"""Per-client request caps: fixed one-minute windows in process memory.

The free tier runs one API instance, so a shared store buys nothing yet.
Keyed on the real client IP as Cloudflare reports it (see _client_key) —
never on request.client.host alone or on X-Forwarded-For, both of which
are an edge/proxy address, not the caller, on this deployment's path.
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


def _client_key(request: Request) -> str:
    """The real client address this request came from.

    This deployment sits behind Cloudflare in front of Render. On that path,
    X-Forwarded-For's rightmost hop is Cloudflare's own edge IP, not the
    caller — keying on it (or on request.client.host, which Render's proxy
    sets to the same edge address) would put every caller in one shared
    bucket, making the limiter useless. Cloudflare sets CF-Connecting-IP to
    the real client IP on every request it proxies; True-Client-IP is the
    equivalent for Enterprise plans with the field enabled. Prefer those,
    never X-Forwarded-For, and fall back to the socket address only when
    neither is present (local dev, no proxy in front).
    """
    cf_connecting_ip = request.headers.get("cf-connecting-ip")
    if cf_connecting_ip:
        return cf_connecting_ip.strip()
    true_client_ip = request.headers.get("true-client-ip")
    if true_client_ip:
        return true_client_ip.strip()
    return request.client.host if request.client else "unknown"


def rate_limit(scope: str, per_minute: int) -> Any:
    def check(request: Request) -> None:
        client = _client_key(request)
        limiter: Limiter = request.app.state.limiter
        if not limiter.allow(scope, client, per_minute):
            raise HTTPException(
                status_code=429,
                detail="too many requests, retry in a minute",
                headers={"x-error-code": "RATE_LIMITED", "Retry-After": str(WINDOW_SECONDS)},
            )

    return Depends(check)
