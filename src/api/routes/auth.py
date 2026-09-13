"""Authentication routes for the government review dashboard."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.dependencies.auth import get_current_user
from src.core.schemas import LoginRequest, LoginResponse, ReviewerProfile
from src.core.security import create_access_token, verify_password
from src.db.models import User, get_session


router = APIRouter(
    prefix="/auth",
    tags=["authentication"],
)


def build_reviewer_profile(user: User) -> ReviewerProfile:
    """Convert a database user into a public reviewer profile."""
    return ReviewerProfile(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
        is_active=user.is_active,
    )


@router.post(
    "/login",
    response_model=LoginResponse,
)
def login(
    request: LoginRequest,
    session: Session = Depends(get_session),
) -> LoginResponse:
    """Authenticate an active government dashboard reviewer."""
    username = request.username.strip().lower()

    if not username or not request.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = session.scalar(
        select(User).where(User.username == username)
    )

    credentials_are_valid = (
        user is not None
        and user.is_active
        and verify_password(request.password, user.password_hash)
    )

    if not credentials_are_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        user_id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
    )

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        reviewer=build_reviewer_profile(user),
    )

@router.get(
    "/me",
    response_model=ReviewerProfile,
    responses={
        401: {
            "description": "Authentication required",
        },
    },
)
def get_my_profile(
    current_user: User = Depends(get_current_user),
) -> ReviewerProfile:
    """Return the profile of the authenticated reviewer."""

    return build_reviewer_profile(current_user)