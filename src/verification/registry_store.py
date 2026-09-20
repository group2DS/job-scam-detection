"""Persistent storage helpers for Hakiki Hire registry administration."""

from __future__ import annotations

import csv
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.core.config import get_settings
from src.db.models import RegistryRecord
from src.verification.registry import normalise


def _read_rows(path: Path) -> list[dict[str, str]]:
    """Read a registry seed CSV into cleaned string dictionaries."""
    if not path.exists():
        return []

    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [
            {
                str(key): str(value or "").strip()
                for key, value in row.items()
                if key is not None
            }
            for row in csv.DictReader(handle)
        ]


def _as_bool(value: str | None, default: bool = True) -> bool:
    """Convert a CSV boolean value safely."""
    if value is None or not value.strip():
        return default

    return value.strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
        "on",
    }


def _company_record(row: dict[str, str]) -> RegistryRecord | None:
    name = row.get("company_name", "").strip()
    if not name:
        return None

    return RegistryRecord(
        category="company",
        external_id=row.get("company_id") or None,
        name=name,
        normalised_name=normalise(name),
        registration_number=row.get("registration_number") or None,
        status=(row.get("status") or "active").lower(),
        county=row.get("county") or None,
        record_is_mock=_as_bool(row.get("record_is_mock")),
        is_active=True,
        created_by="csv-seed",
        updated_by="csv-seed",
    )


def _agency_record(row: dict[str, str]) -> RegistryRecord | None:
    name = row.get("agency_name", "").strip()
    if not name:
        return None

    return RegistryRecord(
        category="agency",
        external_id=row.get("agency_id") or None,
        name=name,
        normalised_name=normalise(name),
        licence_number=row.get("licence_number") or None,
        licence_status=(row.get("licence_status") or "").lower() or None,
        status=(row.get("status") or "active").lower(),
        authorised_destinations=(
            row.get("authorised_destinations") or None
        ),
        county=row.get("county") or None,
        record_is_mock=_as_bool(row.get("record_is_mock")),
        is_active=True,
        created_by="csv-seed",
        updated_by="csv-seed",
    )


def _blacklist_record(row: dict[str, str]) -> RegistryRecord | None:
    value = row.get("value", "").strip()
    if not value:
        return None

    kind = (row.get("kind") or "name").strip().lower()

    return RegistryRecord(
        category="blacklist",
        name=value,
        normalised_name=(
            normalise(value)
            if kind == "name"
            else value.lower()
        ),
        status="listed",
        blacklist_kind=kind,
        blacklist_reason=(
            row.get("reason") or "Listed by regulator"
        ).strip(),
        record_is_mock=_as_bool(row.get("record_is_mock")),
        is_active=True,
        created_by="csv-seed",
        updated_by="csv-seed",
    )


def seed_registry_if_empty(session: Session) -> int:
    """Seed persistent registry records once from the existing CSV files."""
    existing_count = int(
        session.scalar(
            select(func.count()).select_from(RegistryRecord)
        )
        or 0
    )

    if existing_count:
        return 0

    settings = get_settings()
    records: list[RegistryRecord] = []

    for row in _read_rows(settings.company_registry_csv):
        record = _company_record(row)
        if record is not None:
            records.append(record)

    for row in _read_rows(settings.agency_registry_csv):
        record = _agency_record(row)
        if record is not None:
            records.append(record)

    for row in _read_rows(settings.blacklist_csv):
        record = _blacklist_record(row)
        if record is not None:
            records.append(record)

    if not records:
        return 0

    session.add_all(records)
    session.commit()

    return len(records)
