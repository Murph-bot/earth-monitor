"""Cloudflare Turnstile server-side verification (siteverify).

Active only when EM_TURNSTILE_SECRET is set; otherwise verification is a
no-op (dev, tests, deployments without a widget). Fails closed: with a
secret configured, a missing/invalid token is rejected, and so is an
unreachable siteverify endpoint (503, retryable) — never silently allowed.
"""

import requests
import structlog
from fastapi import HTTPException

from app.config import get_settings

log = structlog.get_logger()

SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def verify_turnstile(token: str | None, remote_ip: str | None) -> None:
    secret = get_settings().turnstile_secret
    if not secret:
        return
    if not token:
        raise HTTPException(
            400, "complete the human check and try again", headers={"x-error-code": "TURNSTILE"}
        )
    data = {"secret": secret, "response": token}
    if remote_ip:
        data["remoteip"] = remote_ip
    try:
        resp = requests.post(SITEVERIFY_URL, data=data, timeout=5)
        resp.raise_for_status()
        result = resp.json()
    except (requests.RequestException, ValueError):
        log.warning("turnstile_unreachable")
        raise HTTPException(
            503,
            "human check unavailable, try again in a moment",
            headers={"x-error-code": "TURNSTILE_UNAVAILABLE"},
        ) from None
    if not result.get("success"):
        log.info("turnstile_rejected", codes=result.get("error-codes"))
        raise HTTPException(
            400, "human check failed, try again", headers={"x-error-code": "TURNSTILE"}
        )
