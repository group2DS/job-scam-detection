"""Shared data contracts.

Every stage of the pipeline speaks in these objects. If you are adding a
field, add it here first, then update the stage that populates it. Do not
pass loose dictionaries between stages.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# --------------------------------------------------------------------------
# Enumerations
#
# These are closed sets. The UI renders exactly these values and nothing else.
# Adding a member here means updating the frontend badge map as well.
# --------------------------------------------------------------------------


class RiskLevel(str, Enum):
    """Content risk, derived from the model probability and rule signals."""

    LOWER_RISK = "lower_risk"
    SUSPICIOUS = "suspicious"
    HIGH_RISK = "high_risk"


class VerificationStatus(str, Enum):
    """Entity verification from registry and blacklist lookups.

    Verification is deliberately independent of RiskLevel. A posting can
    read cleanly and still be unverified, and a registered entity can still
    publish a scam.
    """

    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    BLACKLISTED = "blacklisted"
    POSSIBLE_IMPERSONATION = "possible_impersonation"
    NOT_APPLICABLE = "not_applicable"


class EntityType(str, Enum):
    """Identify which registry applies to a posting.

    A direct employer advertising its own vacancy is not a recruitment agency
    and must not be penalised for being absent from an agency register.
    """

    COMPANY = "company"
    AGENCY = "agency"
    UNKNOWN = "unknown"


class ReviewOutcome(str, Enum):
    """Describe how a government reviewer resolved a case."""

    CONFIRMED_LEGITIMATE = "confirmed_legitimate"
    CONFIRMED_SCAM = "confirmed_scam"
    NEEDS_MORE_EVIDENCE = "needs_more_evidence"
    DUPLICATE = "duplicate"
    VERIFIED_BUT_SUSPICIOUS = "verified_but_suspicious"


# --------------------------------------------------------------------------
# Ingestion
# --------------------------------------------------------------------------


class AnalyseRequest(BaseModel):
    """Inbound payload. At least one of URL or text must be supplied."""

    url: Optional[str] = None
    text: Optional[str] = None

    def has_input(self) -> bool:
        """Return whether the request contains a non-empty URL or text."""
        return bool((self.url or "").strip() or (self.text or "").strip())


class Posting(BaseModel):
    """Normalised posting consumed by downstream pipeline stages.

    Missing fields remain None rather than being imputed. Absence can itself
    be a useful signal during analysis.
    """

    title: Optional[str] = None
    description: Optional[str] = None
    requirements: Optional[str] = None
    employer_name: Optional[str] = None
    agency_name: Optional[str] = None
    entity_type: EntityType = EntityType.UNKNOWN
    location: Optional[str] = None
    destination_country: Optional[str] = None
    is_overseas: bool = False
    salary_text: Optional[str] = None
    employment_type: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    application_url: Optional[str] = None
    source_url: Optional[str] = None
    raw_text: str = ""

    def entity_name(self) -> Optional[str]:
        """Return the lookup name, preferring an agency when both exist."""
        return self.agency_name or self.employer_name

    def model_text(self) -> str:
        """Return text assembled in the same order as the training corpus."""
        return " ".join(
            part
            for part in [
                self.title,
                self.description,
                self.requirements,
            ]
            if part
        ).strip()


# --------------------------------------------------------------------------
# Stage outputs
# --------------------------------------------------------------------------


class RuleHit(BaseModel):
    """One deterministic signal that fired."""

    code: str
    label: str
    weight: float = Field(ge=0.0, le=1.0)
    evidence: Optional[str] = None


class ModelResult(BaseModel):
    """Classifier probability output."""

    probability: float = Field(ge=0.0, le=1.0)
    model_version: str
    is_stub: bool = False


class VerificationResult(BaseModel):
    """Registry and blacklist lookup outcome."""

    status: VerificationStatus
    entity_type: EntityType
    entity_name: Optional[str] = None
    matched_name: Optional[str] = None
    match_score: float = 0.0
    registry_id: Optional[str] = None
    blacklist_reason: Optional[str] = None


class Reason(BaseModel):
    """A human-readable explanation produced by a pipeline stage."""

    code: str
    text: str
    source: str


class AnalyseResponse(BaseModel):
    """Analysis information rendered by the job-seeker interface."""

    risk_level: RiskLevel
    verification_status: VerificationStatus
    probability: float
    reasons: list[Reason]
    recommendation: str
    referred_for_review: bool
    case_id: Optional[str] = None
    model_version: str
    analysed_at: datetime


# --------------------------------------------------------------------------
# Government review
# --------------------------------------------------------------------------


class CaseSummary(BaseModel):
    """One row in the government review queue.

    Destination and outcome are exposed here so Overview, Review queue, and
    Reports can derive consistent values from the same filtered case response.
    """

    case_id: str
    entity_name: Optional[str]
    title: Optional[str]
    risk_level: RiskLevel
    verification_status: VerificationStatus
    is_overseas: bool
    created_at: datetime
    review_status: str
    destination_country: Optional[str] = None
    review_outcome: Optional[ReviewOutcome] = None


class CaseDetail(CaseSummary):
    """Full case view, including the assessment that produced it."""

    description: Optional[str]
    location: Optional[str]
    salary_text: Optional[str]
    contact_email: Optional[str]
    probability: float
    reasons: list[Reason]
    review_notes: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    audit_trail: list[str] = Field(default_factory=list)


class ReviewDecision(BaseModel):
    """Reviewer submission. A persisted decision is immutable."""

    outcome: ReviewOutcome
    notes: Optional[str] = None
    reviewer: str = "demo_reviewer"


# --------------------------------------------------------------------------
# Government dashboard authentication
# --------------------------------------------------------------------------


class LoginRequest(BaseModel):
    """Credentials submitted by a government dashboard user."""

    username: str = Field(
        min_length=3,
        max_length=80,
    )
    password: str = Field(
        min_length=8,
        max_length=72,
    )


class ReviewerProfile(BaseModel):
    """Public reviewer information returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str
    role: str
    is_active: bool


class LoginResponse(BaseModel):
    """Successful reviewer login response used by the dashboard."""

    access_token: str
    token_type: str = "bearer"
    reviewer: ReviewerProfile


class TokenResponse(BaseModel):
    """JWT response retained for authentication-client compatibility."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    username: str
    role: str


class UserResponse(BaseModel):
    """Public representation of an authenticated user."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: str
    is_active: bool


class CreateUserRequest(BaseModel):
    """Payload used by an administrator to create a user."""

    username: str = Field(
        min_length=3,
        max_length=80,
    )
    password: str = Field(
        min_length=8,
        max_length=72,
    )
    role: str = Field(
        default="reviewer",
        pattern="^(reviewer|admin)$",
    )
