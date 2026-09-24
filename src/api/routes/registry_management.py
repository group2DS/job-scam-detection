"""Administrator registry-management routes for Hakiki Hire."""

from __future__ import annotations

import json

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from src.api.dependencies.auth import require_admin
from src.verification import registry
from src.verification.registry import normalise
from src.db.models import (
    RegistryAuditEntry,
    RegistryRecord,
    User,
    get_session,
)


router = APIRouter(
    prefix="/registry",
    tags=["registry management"],
)


RegistryCategory = Literal[
    "company",
    "agency",
    "blacklist",
]


class RegistryRecordResponse(BaseModel):
    """Safe registry record returned to an administrator."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    category: str
    external_id: str | None
    name: str
    registration_number: str | None
    licence_number: str | None
    licence_status: str | None
    status: str
    authorised_destinations: str | None
    county: str | None
    blacklist_kind: str | None
    blacklist_reason: str | None
    record_is_mock: bool
    is_active: bool
    created_by: str
    updated_by: str
    created_at: datetime
    updated_at: datetime


@router.get(
    "",
    response_model=list[RegistryRecordResponse],
)
def list_registry_records(
    category: RegistryCategory | None = None,
    search: str | None = Query(
        default=None,
        max_length=200,
    ),
    include_inactive: bool = False,
    session: Session = Depends(get_session),
    current_admin: User = Depends(require_admin),
):
    """List registry records for an authenticated administrator."""
    del current_admin

    statement = select(RegistryRecord)

    if category is not None:
        statement = statement.where(
            RegistryRecord.category == category
        )

    if not include_inactive:
        statement = statement.where(
            RegistryRecord.is_active.is_(True)
        )

    cleaned_search = (search or "").strip().lower()

    if cleaned_search:
        pattern = "%{}%".format(cleaned_search)

        statement = statement.where(
            or_(
                func.lower(RegistryRecord.name).like(pattern),
                func.lower(
                    func.coalesce(
                        RegistryRecord.external_id,
                        "",
                    )
                ).like(pattern),
                func.lower(
                    func.coalesce(
                        RegistryRecord.registration_number,
                        "",
                    )
                ).like(pattern),
                func.lower(
                    func.coalesce(
                        RegistryRecord.licence_number,
                        "",
                    )
                ).like(pattern),
            )
        )

    records = session.scalars(
        statement.order_by(
            RegistryRecord.category.asc(),
            RegistryRecord.name.asc(),
        )
    ).all()

    return [
        RegistryRecordResponse.model_validate(record)
        for record in records
    ]


class RegistryRecordCreateRequest(BaseModel):
    """Administrator request for creating a registry record."""

    category: RegistryCategory
    external_id: str | None = Field(
        default=None,
        max_length=80,
    )
    name: str = Field(
        min_length=2,
        max_length=300,
    )
    registration_number: str | None = Field(
        default=None,
        max_length=120,
    )
    licence_number: str | None = Field(
        default=None,
        max_length=120,
    )
    licence_status: str | None = Field(
        default=None,
        max_length=40,
    )
    status: str = Field(
        default="active",
        min_length=1,
        max_length=40,
    )
    authorised_destinations: str | None = None
    county: str | None = Field(
        default=None,
        max_length=120,
    )
    blacklist_kind: Literal[
        "name",
        "email",
        "phone",
        "domain",
    ] | None = None
    blacklist_reason: str | None = None
    record_is_mock: bool = True

    @field_validator(
        "name",
        "external_id",
        "registration_number",
        "licence_number",
        "licence_status",
        "status",
        "authorised_destinations",
        "county",
        "blacklist_reason",
        mode="before",
    )
    @classmethod
    def clean_text(cls, value):
        if value is None:
            return None

        cleaned = str(value).strip()

        return cleaned or None


def _get_registry_record_or_404(
    session: Session,
    record_id: int,
):
    record = session.get(
        RegistryRecord,
        record_id,
    )

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Registry record not found.",
        )

    return record


def _validate_registry_create_request(
    request: RegistryRecordCreateRequest,
):
    if request.category == "company":
        if not request.external_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Company ID is required.",
            )

        if not request.registration_number:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Company registration number is required.",
            )

    if request.category == "agency":
        if not request.external_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Agency ID is required.",
            )

        if not request.licence_number:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Agency licence number is required.",
            )

    if request.category == "blacklist":
        if not request.blacklist_kind:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Blacklist kind is required.",
            )

        if not request.blacklist_reason:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Blacklist reason is required.",
            )


@router.post(
    "",
    response_model=RegistryRecordResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_registry_record(
    request: RegistryRecordCreateRequest,
    session: Session = Depends(get_session),
    current_admin: User = Depends(require_admin),
):
    """Create a persistent registry record."""

    _validate_registry_create_request(request)

    normalised_name = normalise(request.name)

    existing_name = session.scalar(
        select(RegistryRecord).where(
            RegistryRecord.category == request.category,
            RegistryRecord.normalised_name == normalised_name,
            RegistryRecord.is_active.is_(True),
        )
    )

    if existing_name is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "An active registry record with this name "
                "already exists."
            ),
        )

    if request.external_id:
        existing_identifier = session.scalar(
            select(RegistryRecord).where(
                RegistryRecord.category == request.category,
                func.lower(
                    RegistryRecord.external_id
                ) == request.external_id.lower(),
            )
        )

        if existing_identifier is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "A registry record with this identifier "
                    "already exists."
                ),
            )

    record = RegistryRecord(
        category=request.category,
        external_id=request.external_id,
        name=request.name,
        normalised_name=normalised_name,
        registration_number=request.registration_number,
        licence_number=request.licence_number,
        licence_status=(
            request.licence_status.lower()
            if request.licence_status
            else None
        ),
        status=request.status.lower(),
        authorised_destinations=(
            request.authorised_destinations
        ),
        county=request.county,
        blacklist_kind=request.blacklist_kind,
        blacklist_reason=request.blacklist_reason,
        record_is_mock=request.record_is_mock,
        is_active=True,
        created_by=current_admin.username,
        updated_by=current_admin.username,
    )

    session.add(record)
    session.flush()

    audit = RegistryAuditEntry(
        registry_record_id=record.id,
        actor=current_admin.username,
        action="created",
        record_category=record.category,
        record_name=record.name,
        details_json=json.dumps(
            {
                "external_id": record.external_id,
                "status": record.status,
                "record_is_mock": record.record_is_mock,
            }
        ),
    )

    session.add(audit)
    session.commit()
    session.refresh(record)

    registry.reload_from_database(session)

    return RegistryRecordResponse.model_validate(record)


class RegistryRecordUpdateRequest(BaseModel):
    """Administrator request for editing a registry record."""

    external_id: str | None = Field(
        default=None,
        max_length=80,
    )
    name: str | None = Field(
        default=None,
        min_length=2,
        max_length=300,
    )
    registration_number: str | None = Field(
        default=None,
        max_length=120,
    )
    licence_number: str | None = Field(
        default=None,
        max_length=120,
    )
    licence_status: str | None = Field(
        default=None,
        max_length=40,
    )
    status: str | None = Field(
        default=None,
        min_length=1,
        max_length=40,
    )
    authorised_destinations: str | None = None
    county: str | None = Field(
        default=None,
        max_length=120,
    )
    blacklist_kind: Literal[
        "name",
        "email",
        "phone",
        "domain",
    ] | None = None
    blacklist_reason: str | None = None
    record_is_mock: bool | None = None

    @field_validator(
        "external_id",
        "name",
        "registration_number",
        "licence_number",
        "licence_status",
        "status",
        "authorised_destinations",
        "county",
        "blacklist_reason",
        mode="before",
    )
    @classmethod
    def clean_update_text(cls, value):
        if value is None:
            return None

        cleaned = str(value).strip()

        return cleaned or None


def _validate_registry_record(record: RegistryRecord):
    """Validate required fields after an update is applied."""

    if record.category == "company":
        if not record.external_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Company ID is required.",
            )

        if not record.registration_number:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Company registration number is required.",
            )

    if record.category == "agency":
        if not record.external_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Agency ID is required.",
            )

        if not record.licence_number:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Agency licence number is required.",
            )

    if record.category == "blacklist":
        if not record.blacklist_kind:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Blacklist kind is required.",
            )

        if not record.blacklist_reason:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Blacklist reason is required.",
            )


@router.patch(
    "/{record_id}",
    response_model=RegistryRecordResponse,
)
def update_registry_record(
    record_id: int,
    request: RegistryRecordUpdateRequest,
    session: Session = Depends(get_session),
    current_admin: User = Depends(require_admin),
):
    """Update an existing persistent registry record."""

    record = _get_registry_record_or_404(
        session,
        record_id,
    )

    changes = request.model_dump(
        exclude_unset=True,
    )

    if not changes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one registry field must be supplied.",
        )

    before = {
        "external_id": record.external_id,
        "name": record.name,
        "registration_number": record.registration_number,
        "licence_number": record.licence_number,
        "licence_status": record.licence_status,
        "status": record.status,
        "authorised_destinations": record.authorised_destinations,
        "county": record.county,
        "blacklist_kind": record.blacklist_kind,
        "blacklist_reason": record.blacklist_reason,
        "record_is_mock": record.record_is_mock,
    }

    if "name" in changes:
        if not changes["name"]:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Registry name cannot be empty.",
            )

        updated_normalised_name = normalise(
            changes["name"]
        )

        duplicate_name = session.scalar(
            select(RegistryRecord).where(
                RegistryRecord.category == record.category,
                RegistryRecord.normalised_name
                == updated_normalised_name,
                RegistryRecord.id != record.id,
                RegistryRecord.is_active.is_(True),
            )
        )

        if duplicate_name is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "An active registry record with this name "
                    "already exists."
                ),
            )

        record.name = changes["name"]
        record.normalised_name = updated_normalised_name

    if "external_id" in changes:
        new_external_id = changes["external_id"]

        if new_external_id:
            duplicate_identifier = session.scalar(
                select(RegistryRecord).where(
                    RegistryRecord.category == record.category,
                    func.lower(
                        RegistryRecord.external_id
                    ) == new_external_id.lower(),
                    RegistryRecord.id != record.id,
                )
            )

            if duplicate_identifier is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "A registry record with this identifier "
                        "already exists."
                    ),
                )

        record.external_id = new_external_id

    simple_fields = (
        "registration_number",
        "licence_number",
        "authorised_destinations",
        "county",
        "blacklist_kind",
        "blacklist_reason",
        "record_is_mock",
    )

    for field_name in simple_fields:
        if field_name in changes:
            setattr(
                record,
                field_name,
                changes[field_name],
            )

    if "licence_status" in changes:
        record.licence_status = (
            changes["licence_status"].lower()
            if changes["licence_status"]
            else None
        )

    if "status" in changes:
        if not changes["status"]:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Registry status cannot be empty.",
            )

        record.status = changes["status"].lower()

    _validate_registry_record(record)

    record.updated_by = current_admin.username

    after = {
        "external_id": record.external_id,
        "name": record.name,
        "registration_number": record.registration_number,
        "licence_number": record.licence_number,
        "licence_status": record.licence_status,
        "status": record.status,
        "authorised_destinations": record.authorised_destinations,
        "county": record.county,
        "blacklist_kind": record.blacklist_kind,
        "blacklist_reason": record.blacklist_reason,
        "record_is_mock": record.record_is_mock,
    }

    changed_values = {
        field_name: {
            "before": before[field_name],
            "after": after[field_name],
        }
        for field_name in after
        if before[field_name] != after[field_name]
    }

    if not changed_values:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The registry record already contains these values.",
        )

    session.add(record)
    session.flush()

    session.add(
        RegistryAuditEntry(
            registry_record_id=record.id,
            actor=current_admin.username,
            action="updated",
            record_category=record.category,
            record_name=record.name,
            details_json=json.dumps(
                changed_values,
                default=str,
            ),
        )
    )

    session.commit()
    session.refresh(record)

    registry.reload_from_database(session)

    return RegistryRecordResponse.model_validate(record)


class RegistryRecordStatusRequest(BaseModel):
    """Administrator request for activating or deactivating a record."""

    is_active: bool


@router.patch(
    "/{record_id}/status",
    response_model=RegistryRecordResponse,
)
def update_registry_record_status(
    record_id: int,
    request: RegistryRecordStatusRequest,
    session: Session = Depends(get_session),
    current_admin: User = Depends(require_admin),
):
    """Activate or deactivate a persistent registry record."""

    record = _get_registry_record_or_404(
        session,
        record_id,
    )

    if record.is_active == request.is_active:
        state = (
            "active"
            if request.is_active
            else "inactive"
        )

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "The registry record is already {}."
            ).format(state),
        )

    previous_status = record.is_active
    record.is_active = request.is_active
    record.updated_by = current_admin.username

    action = (
        "activated"
        if request.is_active
        else "deactivated"
    )

    session.add(record)
    session.flush()

    session.add(
        RegistryAuditEntry(
            registry_record_id=record.id,
            actor=current_admin.username,
            action=action,
            record_category=record.category,
            record_name=record.name,
            details_json=json.dumps(
                {
                    "is_active": {
                        "before": previous_status,
                        "after": request.is_active,
                    }
                }
            ),
        )
    )

    session.commit()
    session.refresh(record)

    registry.reload_from_database(session)

    return RegistryRecordResponse.model_validate(record)


class RegistryAuditEntryResponse(BaseModel):
    """One append-only Registry Management audit event."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    registry_record_id: int | None
    actor: str
    action: str
    record_category: str
    record_name: str
    details_json: str
    created_at: datetime


@router.get(
    "/{record_id}/audit",
    response_model=list[RegistryAuditEntryResponse],
)
def list_registry_audit_history(
    record_id: int,
    session: Session = Depends(get_session),
    current_admin: User = Depends(require_admin),
):
    """Return the complete audit history for one registry record."""

    del current_admin

    _get_registry_record_or_404(
        session,
        record_id,
    )

    entries = session.scalars(
        select(RegistryAuditEntry)
        .where(
            RegistryAuditEntry.registry_record_id
            == record_id
        )
        .order_by(
            RegistryAuditEntry.created_at.desc(),
            RegistryAuditEntry.id.desc(),
        )
    ).all()

    return [
        RegistryAuditEntryResponse.model_validate(entry)
        for entry in entries
    ]
