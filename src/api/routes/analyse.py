"""
POST /api/analyse

The single entry point for the job seeker interface. Orchestrates the
pipeline and, where warranted, creates a government review case.

The orchestration is deliberately flat and readable: each stage is one call,
and the order is the order described in the architecture document.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.core.schemas import AnalyseRequest, AnalyseResponse
from src.db.models import AuditEntry, ReviewCase, get_session
from src.decision import layer
from src.ingestion import extractor
from src.models import classifier
from src.rules import engine
from src.verification import registry

log = logging.getLogger(__name__)
router = APIRouter(tags=["analyse"])


@router.post("/analyse", response_model=AnalyseResponse)
def analyse(
    payload: AnalyseRequest,
    session: Session = Depends(get_session),
) -> AnalyseResponse:
    if not payload.has_input():
        raise HTTPException(
            status_code=422,
            detail="Provide either a listing URL or the job description text.",
        )

    # 1. Ingestion. URL is best effort; pasted text is the reliable path.
    posting = None
    if payload.url:
        posting = extractor.from_url(payload.url)
        if posting is None and not payload.text:
            raise HTTPException(
                status_code=422,
                detail=(
                    "That page could not be read automatically. Please paste "
                    "the job description text instead."
                ),
            )
    if posting is None:
        posting = extractor.from_text(payload.text or "", source_url=payload.url)

    # 2. Content risk. Text only; the model never sees registry data.
    model_result = classifier.predict(posting.model_text() or posting.raw_text)

    # 3. Deterministic signals.
    hits = engine.evaluate(posting)
    overseas = engine.looks_overseas(posting)

    # 4. Entity verification, independent of the model.
    verification = registry.verify(posting)

    # 5. Fuse.
    risk, reasons, recommendation, refer, score = layer.combine(
        posting, model_result, hits, verification, overseas
    )

    # 6. Refer if warranted.
    case_id = None
    if refer:
        case = ReviewCase(
            title=posting.title,
            description=posting.description,
            entity_name=posting.entity_name(),
            entity_type=verification.entity_type.value,
            location=posting.location,
            destination_country=posting.destination_country,
            is_overseas=overseas,
            salary_text=posting.salary_text,
            contact_email=posting.contact_email,
            contact_phone=posting.contact_phone,
            source_url=posting.source_url,
            risk_level=risk.value,
            verification_status=verification.status.value,
            probability=score,
            model_version=model_result.model_version,
        )
        case.reasons = [reason.model_dump() for reason in reasons]
        session.add(case)
        session.flush()
        session.add(
            AuditEntry(
                case_id=case.case_id,
                actor="system",
                action=(
                    f"Case created. Risk {risk.value}, "
                    f"verification {verification.status.value}, "
                    f"probability {score:.2f}."
                ),
            )
        )
        session.commit()
        case_id = case.case_id

    return AnalyseResponse(
        risk_level=risk,
        verification_status=verification.status,
        probability=score,
        reasons=reasons,
        recommendation=recommendation,
        referred_for_review=refer,
        case_id=case_id,
        model_version=model_result.model_version,
        analysed_at=datetime.now(timezone.utc),
    )
