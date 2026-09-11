"""
POST /api/analyse       submit a URL or pasted text
POST /api/analyse/file  submit a PDF, Word or text document

The single entry point for the job seeker interface. Orchestrates the
pipeline and, where warranted, creates a government review case.

The orchestration is deliberately flat and readable: each stage is one call,
and the order is the order described in the architecture document.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from src.core.schemas import AnalyseRequest, AnalyseResponse, Posting
from src.db.models import AuditEntry, ReviewCase, get_session
from src.decision import layer
from src.ingestion import extractor, files
from src.models import classifier
from src.rules import engine
from src.verification import registry

log = logging.getLogger(__name__)
router = APIRouter(tags=["analyse"])

# Below this, there is not enough text to say anything meaningful. Returning a
# confident looking result from a few characters would be worse than refusing.
MIN_CHARS = 40


def _assess(posting: Posting, session: Session) -> AnalyseResponse:
    """Run the pipeline on a normalised posting and build the response.

    Shared by every entry point so that pasted text, a fetched URL and an
    uploaded document all follow exactly the same path.
    """
    # 1. Content risk. Text only; the model never sees registry data.
    model_result = classifier.predict(posting.model_text() or posting.raw_text)

    # 2. Deterministic signals.
    hits = engine.evaluate(posting)
    overseas = engine.looks_overseas(posting)

    # 3. Entity verification, independent of the model.
    verification = registry.verify(posting)

    # 4. Fuse.
    risk, reasons, recommendation, refer, score = layer.combine(
        posting, model_result, hits, verification, overseas
    )

    # 5. Refer if warranted.
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


@router.post("/analyse", response_model=AnalyseResponse)
def analyse(
    payload: AnalyseRequest,
    session: Session = Depends(get_session),
) -> AnalyseResponse:
    if not payload.has_input():
        raise HTTPException(
            status_code=422,
            detail="Provide either a listing link or the job description text.",
        )

    # Ingestion. URL is best effort; pasted text is the reliable path.
    posting = None
    if payload.url:
        try:
            posting = extractor.from_url(payload.url)
        except extractor.FetchFailed as exc:
            # A page we cannot read is a usability problem, not a fraud
            # signal. Fall back to pasted text if it was supplied, otherwise
            # tell the person why and ask for a paste.
            if not payload.text:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            log.info("URL fetch failed, using supplied text: %s", exc)
    if posting is None:
        text = (payload.text or "").strip()
        if len(text) < MIN_CHARS:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Please paste more of the listing. At least a sentence or "
                    "two is needed to assess it."
                ),
            )
        posting = extractor.from_text(text, source_url=payload.url)

    return _assess(posting, session)


@router.post("/analyse/file", response_model=AnalyseResponse)
async def analyse_file(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> AnalyseResponse:
    """Assess a job listing supplied as a document.

    People are frequently sent an offer as a PDF or Word attachment, which is
    exactly the case where they cannot easily copy the text out.
    """
    data = await file.read()

    try:
        text = files.extract(file.filename or "", data, min_chars=MIN_CHARS)
    except files.ExtractionError as exc:
        # These messages are written for the person who uploaded the file.
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    posting = extractor.from_text(text)
    return _assess(posting, session)


@router.get("/analyse/formats", tags=["analyse"])
def supported_formats() -> dict:
    """Lets the interface list supported formats without hard coding them."""
    return {
        "extensions": sorted(files.SUPPORTED),
        "descriptions": files.SUPPORTED,
        "max_bytes": files.MAX_BYTES,
        "min_chars": MIN_CHARS,
    }
