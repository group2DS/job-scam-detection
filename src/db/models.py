"""
Database layer.

Only review cases and their audit entries are persisted. Job seeker
submissions that are not referred are analysed and discarded, which is what
the interface promises when it says data is not stored.

Registries are read from CSV at startup rather than stored here, so the team
can update reference data without a migration.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
)

from src.core.config import get_settings


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_case_id() -> str:
    return f"C-{uuid.uuid4().hex[:6].upper()}"


class Base(DeclarativeBase):
    pass

class User(Base):
    """An authenticated government dashboard user."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    username: Mapped[str] = mapped_column(
        String(80),
        unique=True,
        index=True,
        nullable=False,
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    display_name: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    role: Mapped[str] = mapped_column(
        String(30),
        default="reviewer",
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_now,
        nullable=False,
    )


class ReviewCase(Base):
    """A posting referred for government review.

    Stores the full assessment that produced the referral, so a reviewer can
    see what the system concluded and why, and so the decision can later be
    audited against the model version that made it.
    """

    __tablename__ = "review_cases"

    case_id: Mapped[str] = mapped_column(String(16), primary_key=True, default=_new_case_id)

    # Posting snapshot, captured at submission time.
    title: Mapped[str | None] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    entity_name: Mapped[str | None] = mapped_column(String(200), index=True)
    entity_type: Mapped[str] = mapped_column(String(20), default="unknown")
    location: Mapped[str | None] = mapped_column(String(120))
    destination_country: Mapped[str | None] = mapped_column(String(80))
    is_overseas: Mapped[bool] = mapped_column(Boolean, default=False)
    salary_text: Mapped[str | None] = mapped_column(String(120))
    contact_email: Mapped[str | None] = mapped_column(String(200))
    contact_phone: Mapped[str | None] = mapped_column(String(40))
    source_url: Mapped[str | None] = mapped_column(String(500))

    # System assessment.
    risk_level: Mapped[str] = mapped_column(String(20), index=True)
    verification_status: Mapped[str] = mapped_column(String(30), index=True)
    probability: Mapped[float] = mapped_column(Float)
    model_version: Mapped[str] = mapped_column(String(40), default="unknown")
    reasons_json: Mapped[str] = mapped_column(Text, default="[]")

    # Review state.
    review_status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    review_outcome: Mapped[str | None] = mapped_column(String(40))
    review_notes: Mapped[str | None] = mapped_column(Text)
    reviewer: Mapped[str | None] = mapped_column(String(80))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    audit_entries: Mapped[list["AuditEntry"]] = relationship(
        back_populates="case",
        cascade="all, delete-orphan",
        order_by="AuditEntry.created_at",
    )

    @property
    def reasons(self) -> list[dict]:
        return json.loads(self.reasons_json or "[]")

    @reasons.setter
    def reasons(self, value: list[dict]) -> None:
        self.reasons_json = json.dumps(value)


class AuditEntry(Base):
    """An append only record of what happened to a case.

    Never updated or deleted. A reviewer decision is written once; correcting
    it means adding a new entry, not editing the old one.
    """

    __tablename__ = "audit_entries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("review_cases.case_id"), index=True)
    actor: Mapped[str] = mapped_column(String(80), default="system")
    action: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    case: Mapped[ReviewCase] = relationship(back_populates="audit_entries")


_settings = get_settings()
_connect_args = (
    {"check_same_thread": False} if _settings.database_url.startswith("sqlite") else {}
)
engine = create_engine(_settings.database_url, connect_args=_connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(engine)


def get_session():
    """FastAPI dependency yielding a scoped session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
