"""Authentication dependencies for protected Hakiki Hire API routes."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from src.core.security import decode_access_token
from src.db.models import User, get_session

bearer_scheme = HTTPBearer(auto_error=False)


def _credentials_error(
    detail: str = "Invalid or expired access token.",
) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: Session = Depends(get_session),
) -> User:
    """Return the active database user represented by a bearer token."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _credentials_error("Authentication is required.")

    try:
        payload = decode_access_token(credentials.credentials)
    except Exception as exc:
        raise _credentials_error() from exc

    if not isinstance(payload, dict):
        raise _credentials_error()

    raw_user_id = payload.get("sub") or payload.get("user_id")
    if raw_user_id is None:
        raise _credentials_error()

    try:
        user_id = int(raw_user_id)
    except (TypeError, ValueError) as exc:
        raise _credentials_error() from exc

    user = session.get(User, user_id)
    if user is None:
        raise _credentials_error(
            "The authenticated Hakiki Hire account no longer exists."
        )
    if not user.is_active:
        raise _credentials_error("This account is inactive.")

    token_username = payload.get("username")
    if token_username and token_username != user.username:
        raise _credentials_error()

    return user


def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Allow access only to active Hakiki Hire administrators."""
    if not current_user.is_active:
        raise _credentials_error("This account is inactive.")
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access is required.",
        )
    return current_user
