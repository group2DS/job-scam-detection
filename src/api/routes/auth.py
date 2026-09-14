"""Authentication and administrator access-management routes for Hakiki Hire."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.api.dependencies.auth import get_current_user, require_admin
from src.core.security import create_access_token, hash_password, verify_password
from src.db.models import User, get_session


router = APIRouter(
    prefix="/auth",
    tags=["authentication"],
)


class LoginRequest(BaseModel):
    """Credentials submitted by an authorised Hakiki Hire user."""

    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if not cleaned:
            raise ValueError("Username is required.")
        return cleaned


class UserAccessProfile(BaseModel):
    """Safe account information returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str
    role: str
    is_active: bool


class LoginResponse(BaseModel):
    """Successful Hakiki Hire login response."""

    access_token: str
    token_type: str = "bearer"
    reviewer: UserAccessProfile


class UserCreateRequest(BaseModel):
    """Administrator request for creating an authorised account."""

    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=10, max_length=200)
    display_name: str = Field(min_length=2, max_length=120)
    role: Literal["admin", "reviewer"] = "reviewer"
    is_active: bool = True

    @field_validator("username")
    @classmethod
    def normalize_new_username(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if not cleaned:
            raise ValueError("Username is required.")
        return cleaned

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Display name is required.")
        return cleaned


class UserStatusUpdateRequest(BaseModel):
    """Administrator request for changing account status."""

    is_active: bool


class UserRoleUpdateRequest(BaseModel):
    """Administrator request for changing an account role."""

    role: Literal["admin", "reviewer"]


def _profile(user: User) -> UserAccessProfile:
    """Convert a database user into a safe public profile."""
    return UserAccessProfile.model_validate(user)


def _get_user_or_404(session: Session, user_id: int) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User account not found.",
        )
    return user


def _active_admin_count(session: Session) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(User)
            .where(
                User.role == "admin",
                User.is_active.is_(True),
            )
        )
        or 0
    )


@router.post(
    "/login",
    response_model=LoginResponse,
)
def login(
    request: LoginRequest,
    session: Session = Depends(get_session),
) -> LoginResponse:
    """Authenticate an active Hakiki Hire account and issue a token."""
    user = session.scalar(
        select(User).where(
            func.lower(User.username) == request.username
        )
    )

    if (
        user is None
        or not user.is_active
        or not verify_password(request.password, user.password_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(
        user_id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
    )

    return LoginResponse(
        access_token=token,
        reviewer=_profile(user),
    )


@router.get(
    "/me",
    response_model=UserAccessProfile,
)
def get_my_profile(
    current_user: User = Depends(get_current_user),
) -> UserAccessProfile:
    """Return the currently authenticated account."""
    return _profile(current_user)


@router.get(
    "/users",
    response_model=list[UserAccessProfile],
)
def list_users(
    session: Session = Depends(get_session),
    current_admin: User = Depends(require_admin),
) -> list[UserAccessProfile]:
    """Return authorised Hakiki Hire accounts to an administrator."""
    del current_admin

    users = session.scalars(
        select(User).order_by(
            User.display_name.asc(),
            User.username.asc(),
        )
    ).all()

    return [_profile(user) for user in users]


@router.post(
    "/users",
    response_model=UserAccessProfile,
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    request: UserCreateRequest,
    session: Session = Depends(get_session),
    current_admin: User = Depends(require_admin),
) -> UserAccessProfile:
    """Create a Hakiki Hire administrator or reviewer account."""
    del current_admin

    existing_user = session.scalar(
        select(User).where(
            func.lower(User.username) == request.username
        )
    )
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this username already exists.",
        )

    user = User(
        username=request.username,
        password_hash=hash_password(request.password),
        display_name=request.display_name,
        role=request.role,
        is_active=request.is_active,
    )

    session.add(user)
    session.commit()
    session.refresh(user)

    return _profile(user)


@router.patch(
    "/users/{user_id}/status",
    response_model=UserAccessProfile,
)
def update_user_status(
    user_id: int,
    request: UserStatusUpdateRequest,
    session: Session = Depends(get_session),
    current_admin: User = Depends(require_admin),
) -> UserAccessProfile:
    """Activate or deactivate an authorised account."""
    user = _get_user_or_404(session, user_id)

    if user.id == current_admin.id and not request.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You cannot deactivate your own account.",
        )

    if (
        user.role == "admin"
        and user.is_active
        and not request.is_active
        and _active_admin_count(session) <= 1
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The last active administrator cannot be deactivated.",
        )

    user.is_active = request.is_active
    session.add(user)
    session.commit()
    session.refresh(user)

    return _profile(user)


@router.patch(
    "/users/{user_id}/role",
    response_model=UserAccessProfile,
)
def update_user_role(
    user_id: int,
    request: UserRoleUpdateRequest,
    session: Session = Depends(get_session),
    current_admin: User = Depends(require_admin),
) -> UserAccessProfile:
    """Change an authorised account's role."""
    user = _get_user_or_404(session, user_id)

    if user.id == current_admin.id and request.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You cannot remove your own administrator role.",
        )

    if (
        user.role == "admin"
        and request.role != "admin"
        and user.is_active
        and _active_admin_count(session) <= 1
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The last active administrator cannot be demoted.",
        )

    user.role = request.role
    session.add(user)
    session.commit()
    session.refresh(user)

    return _profile(user)
