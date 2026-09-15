"""Authentication security utilities for government reviewers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from src.core.config import get_settings


class AuthenticationError(Exception):
    """Raised when authentication credentials or tokens are invalid."""


def _normalise_password(password: str) -> bytes:
    """Validate and convert a password into bytes for bcrypt."""
    if not isinstance(password, str):
        raise ValueError("Password must be a string.")

    if not password:
        raise ValueError("Password is required.")

    password_bytes = password.encode("utf-8")

    if len(password_bytes) > 72:
        raise ValueError("Password must not exceed 72 bytes.")

    return password_bytes


def hash_password(password: str) -> str:
    """Create a bcrypt hash for a plain-text password."""
    password_bytes = _normalise_password(password)
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Return True when a password matches its stored bcrypt hash."""
    if not isinstance(password_hash, str) or not password_hash.strip():
        return False

    try:
        password_bytes = _normalise_password(plain_password)
        return bcrypt.checkpw(
            password_bytes,
            password_hash.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False


def create_access_token(
    *,
    user_id: int,
    username: str,
    display_name: str,
    role: str,
    expires_minutes: int | None = None,
) -> str:
    """Create a signed JWT access token for a reviewer."""
    settings = get_settings()

    if expires_minutes is None:
        expires_minutes = settings.access_token_expire_minutes

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=expires_minutes)

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "username": username,
        "display_name": display_name,
        "role": role,
        "iat": now,
        "exp": expires_at,
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a signed reviewer access token."""
    settings = get_settings()

    if not isinstance(token, str) or not token.strip():
        raise AuthenticationError("Invalid authentication token.")

    try:
        payload = jwt.decode(
            token.strip(),
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError(
            "Authentication token has expired."
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError(
            "Invalid authentication token."
        ) from exc

    required_claims = {
        "sub",
        "username",
        "display_name",
        "role",
        "iat",
        "exp",
    }
    missing_claims = required_claims.difference(payload.keys())

    if missing_claims:
        raise AuthenticationError(
            "Authentication token is missing required information."
        )

    try:
        payload["user_id"] = int(payload["sub"])
    except (TypeError, ValueError) as exc:
        raise AuthenticationError(
            "Authentication token contains an invalid user identifier."
        ) from exc

    return payload
