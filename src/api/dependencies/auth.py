"""FastAPI dependencies for authenticated government reviewers."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from src.core.security import AuthenticationError, decode_access_token
from src.db.models import User, get_session


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: Session = Depends(get_session),
) -> User:
    """Return the active reviewer represented by a valid bearer token."""
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication is required.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized

    try:
        payload = decode_access_token(credentials.credentials)
    except AuthenticationError as exc:
        raise unauthorized from exc

    user = session.get(User, payload["user_id"])

    if user is None or not user.is_active:
        raise unauthorized

    if user.username != payload["username"]:
        raise unauthorized

    return user
