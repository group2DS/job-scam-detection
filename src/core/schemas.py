"""
Shared data contracts.

Every stage of the pipeline speaks in these objects. If you are adding a
field, add it here first, then update the stage that populates it. Do not
pass loose dicts between stages.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


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
    """Entity verification, derived from registry and blacklist lookups.

    Deliberately independent of RiskLevel. A posting can read cleanly and
    still be unverified, and a registered entity can still publish a scam.
    """

    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    BLACKLISTED = "blacklisted"
    POSSIBLE_IMPERSONATION = "possible_impersonation"
    NOT_APPLICABLE = "not_applicable"


class EntityType(str, Enum):
    """Which registry applies to this posting.

    A direct employer advertising its own vacancy is not a recruitment agency
    and must not be penalised for being absent from an agency register.
    """

    COMPANY = "company"
    AGENCY = "agency"
    UNKNOWN = "unknown"


class ReviewOutcome(str, Enum):
    """How a government reviewer resolved a case.

    Five outcomes rather than two, because real cases are not cleanly
    legitimate or fraudulent and forcing a binary produces bad labels.
    """

    CONFIRMED_LEGITIMATE = "confirmed_legitimate"
    CONFIRMED_SCAM = "confirmed_scam"
    NEEDS_MORE_EVIDENCE = "needs_more_evidence"
    DUPLICATE = "duplicate"
    VERIFIED_BUT_SUSPICIOUS = "verified_but_suspicious"


# --------------------------------------------------------------------------
# Ingestion
# --------------------------------------------------------------------------


class AnalyseRequest(BaseModel):
    """Inbound payload. Exactly one of url or text must be supplied."""

    url: Optional[str] = None
    text: Optional[str] = None

    def has_input(self) -> bool:
        return bool((self.url or "").strip() or (self.text or "").strip())


class Posting(BaseModel):
    """Normalised posting. Every downstream stage reads this, never raw input.

    Missing fields stay None rather than being imputed. Absence is itself a
    signal: company is null for roughly two thirds of known fraudulent ads.
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
        """The name to look up, preferring the agency when both are present."""
        return self.agency_name or self.employer_name

    def model_text(self) -> str:
        """Concatenated text handed to the classifier.

        Mirrors how the training corpus was assembled: title, description and
        requirements joined with a single space. If this drifts from the
        training construction the vectoriser sees a different distribution at
        inference time, and nothing will raise an error.
        """
        return " ".join(
            p for p in [self.title, self.description, self.requirements] if p
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
    """Classifier output. A probability and nothing else.

    The model does not see registry data and does not assign a tier.
    """

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
    """A single human readable explanation line.

    Reasons are the product. A bare score tells a job seeker nothing they
    can act on; naming the fee request lets them recognise the pattern again.
    """

    code: str
    text: str
    source: str  # model | rule | registry


class AnalyseResponse(BaseModel):
    """What the job seeker UI renders."""

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
    """One row in the review queue."""

    case_id: str
    entity_name: Optional[str]
    title: Optional[str]
    risk_level: RiskLevel
    verification_status: VerificationStatus
    is_overseas: bool
    created_at: datetime
    review_status: str


class CaseDetail(CaseSummary):
    """Full case view, including the assessment that produced it."""

    description: Optional[str]
    location: Optional[str]
    destination_country: Optional[str]
    salary_text: Optional[str]
    contact_email: Optional[str]
    probability: float
    reasons: list[Reason]
    review_outcome: Optional[ReviewOutcome] = None
    review_notes: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    audit_trail: list[str] = []


class ReviewDecision(BaseModel):
    """Reviewer submission. Immutable once written."""

    outcome: ReviewOutcome
    notes: Optional[str] = None
    reviewer: str = "demo_reviewer"
