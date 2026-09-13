"""Government review endpoints.

The dashboard reads from the same database that the analysis endpoint writes
to. Referred cases are therefore immediately available to authenticated
government reviewers.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.api.dependencies.auth import get_current_user
from src.core.schemas import CaseDetail, CaseSummary, Reason, ReviewDecision
from src.db.models import AuditEntry, ReviewCase, User, get_session


router = APIRouter(tags=["cases"])


@router.get("/cases", response_model=list[CaseSummary])
def list_cases(
    risk_level: str | None = Query(
        default=None,
        description="lower_risk|suspicious|high_risk",
    ),
    review_status: str | None = Query(
        default=None,
        description="open|resolved",
    ),
    is_overseas: bool | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[CaseSummary]:
    """Return referred cases visible to an authenticated reviewer."""
    del current_user

    statement = select(ReviewCase).order_by(
        ReviewCase.created_at.desc()
    )

    if risk_level:
        statement = statement.where(
            ReviewCase.risk_level == risk_level
        )

    if review_status:
        statement = statement.where(
            ReviewCase.review_status == review_status
        )

    if is_overseas is not None:
        statement = statement.where(
            ReviewCase.is_overseas == is_overseas
        )

    cases = session.scalars(statement.limit(limit)).all()

    return [
        CaseSummary(
            case_id=case.case_id,
            entity_name=case.entity_name,
            title=case.title,
            risk_level=case.risk_level,
            verification_status=case.verification_status,
            is_overseas=case.is_overseas,
            created_at=case.created_at,
            review_status=case.review_status,
        )
        for case in cases
    ]


@router.get("/cases/stats")
def case_stats(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return summary counts for the dashboard header."""
    del current_user

    total = (
        session.scalar(
            select(func.count()).select_from(ReviewCase)
        )
        or 0
    )

    open_cases = (
        session.scalar(
            select(func.count())
            .select_from(ReviewCase)
            .where(ReviewCase.review_status == "open")
        )
        or 0
    )

    by_risk = dict(
        session.execute(
            select(
                ReviewCase.risk_level,
                func.count(),
            ).group_by(ReviewCase.risk_level)
        ).all()
    )

    overseas = (
        session.scalar(
            select(func.count())
            .select_from(ReviewCase)
            .where(ReviewCase.is_overseas.is_(True))
        )
        or 0
    )

    return {
        "total_cases": total,
        "open_cases": open_cases,
        "resolved_cases": total - open_cases,
        "high_risk": by_risk.get("high_risk", 0),
        "suspicious": by_risk.get("suspicious", 0),
        "overseas_cases": overseas,
    }


def _to_detail(case: ReviewCase) -> CaseDetail:
    """Convert a persisted review case into its API representation."""
    return CaseDetail(
        case_id=case.case_id,
        entity_name=case.entity_name,
        title=case.title,
        risk_level=case.risk_level,
        verification_status=case.verification_status,
        is_overseas=case.is_overseas,
        created_at=case.created_at,
        review_status=case.review_status,
        description=case.description,
        location=case.location,
        destination_country=case.destination_country,
        salary_text=case.salary_text,
        contact_email=case.contact_email,
        probability=case.probability,
        reasons=[Reason(**item) for item in case.reasons],
        review_outcome=case.review_outcome,
        review_notes=case.review_notes,
        reviewed_at=case.reviewed_at,
        audit_trail=[
            (
                f"{entry.created_at:%d %b %Y %H:%M}  "
                f"{entry.actor}  {entry.action}"
            )
            for entry in case.audit_entries
        ],
    )


@router.get("/cases/{case_id}", response_model=CaseDetail)
def get_case(
    case_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CaseDetail:
    """Return one referred case to an authenticated reviewer."""
    del current_user

    case = session.get(ReviewCase, case_id)

    if case is None:
        raise HTTPException(
            status_code=404,
            detail="Case not found.",
        )

    return _to_detail(case)


@router.post(
    "/cases/{case_id}/decision",
    response_model=CaseDetail,
)
def submit_decision(
    case_id: str,
    decision: ReviewDecision,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CaseDetail:
    """Record a final decision using the authenticated reviewer identity."""
    case = session.get(ReviewCase, case_id)

    if case is None:
        raise HTTPException(
            status_code=404,
            detail="Case not found.",
        )

    if case.review_status == "resolved":
        raise HTTPException(
            status_code=409,
            detail=(
                "This case has already been resolved "
                "and cannot be edited."
            ),
        )

    case.review_outcome = decision.outcome.value
    case.review_notes = decision.notes
    case.reviewer = current_user.display_name
    case.reviewed_at = datetime.now(timezone.utc)
    case.review_status = "resolved"

    session.add(
        AuditEntry(
            case_id=case.case_id,
            actor=current_user.username,
            action=(
                "Decision recorded: {}.".format(
                    decision.outcome.value
                )
            ),
        )
    )

    session.commit()
    session.refresh(case)

    return _to_detail(case)
