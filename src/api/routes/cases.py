"""
Government review endpoints.

The dashboard reads from the same database the analysis endpoint writes to.
That is the whole referral mechanism: no queue, no integration layer, nothing
that can fail during a demonstration.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.core.schemas import CaseDetail, CaseSummary, Reason, ReviewDecision
from src.db.models import AuditEntry, ReviewCase, get_session

router = APIRouter(tags=["cases"])


@router.get("/cases", response_model=list[CaseSummary])
def list_cases(
    risk_level: str | None = Query(None, description="lower_risk|suspicious|high_risk"),
    review_status: str | None = Query(None, description="open|resolved"),
    is_overseas: bool | None = None,
    limit: int = Query(50, le=200),
    session: Session = Depends(get_session),
) -> list[CaseSummary]:
    stmt = select(ReviewCase).order_by(ReviewCase.created_at.desc())

    if risk_level:
        stmt = stmt.where(ReviewCase.risk_level == risk_level)
    if review_status:
        stmt = stmt.where(ReviewCase.review_status == review_status)
    if is_overseas is not None:
        stmt = stmt.where(ReviewCase.is_overseas == is_overseas)

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
        for case in session.scalars(stmt.limit(limit))
    ]


@router.get("/cases/stats")
def case_stats(session: Session = Depends(get_session)) -> dict:
    """Summary tiles for the dashboard header."""
    total = session.scalar(select(func.count()).select_from(ReviewCase)) or 0
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
            select(ReviewCase.risk_level, func.count()).group_by(ReviewCase.risk_level)
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
            f"{entry.created_at:%d %b %Y %H:%M}  {entry.actor}  {entry.action}"
            for entry in case.audit_entries
        ],
    )


@router.get("/cases/{case_id}", response_model=CaseDetail)
def get_case(case_id: str, session: Session = Depends(get_session)) -> CaseDetail:
    case = session.get(ReviewCase, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found.")
    return _to_detail(case)


@router.post("/cases/{case_id}/decision", response_model=CaseDetail)
def submit_decision(
    case_id: str,
    decision: ReviewDecision,
    session: Session = Depends(get_session),
) -> CaseDetail:
    """Record a reviewer decision.

    Decisions are written once and cannot be edited. Reopening a case means
    adding a new audit entry, which preserves the original judgement.
    """
    case = session.get(ReviewCase, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found.")
    if case.review_status == "resolved":
        raise HTTPException(
            status_code=409,
            detail="This case has already been resolved and cannot be edited.",
        )

    case.review_outcome = decision.outcome.value
    case.review_notes = decision.notes
    case.reviewer = decision.reviewer
    case.reviewed_at = datetime.now(timezone.utc)
    case.review_status = "resolved"

    session.add(
        AuditEntry(
            case_id=case.case_id,
            actor=decision.reviewer,
            action=f"Decision recorded: {decision.outcome.value}.",
        )
    )
    session.commit()
    session.refresh(case)
    return _to_detail(case)
