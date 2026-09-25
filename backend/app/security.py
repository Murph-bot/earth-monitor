"""Password hashing + JWT issuing/verification.

Passwords: PBKDF2-HMAC-SHA256, 600k iterations (OWASP floor for SHA-256),
random 16-byte salt — stdlib only, NIST-approved. Stored format:
``pbkdf2$<iters>$<salt_hex>$<hash_hex>`` — self-describing so parameters
can rotate without a migration.

Tokens: HS256 JWT, sub=user_id, 14-day expiry. One secret, one algorithm —
no JWKS machinery until a second issuer exists.
"""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt

from app.config import get_settings

_ALGO = "HS256"
_ITERS = 600_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERS)
    return f"pbkdf2${_ITERS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _scheme, iters, salt_hex, hash_hex = stored.split("$", 3)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iters))
    except (ValueError, TypeError, AttributeError):
        return False
    return secrets.compare_digest(dk.hex(), hash_hex)


def issue_token(user_id: uuid.UUID) -> str:
    s = get_settings()
    now = datetime.now(UTC)
    return jwt.encode(
        {"sub": str(user_id), "iat": now, "exp": now + timedelta(hours=s.jwt_ttl_hours)},
        s.jwt_secret,
        algorithm=_ALGO,
    )


def decode_token(token: str) -> uuid.UUID | None:
    """Returns the user id, or None for any invalid/expired token."""
    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=[_ALGO])
        return uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
