"""
Entity verification against registry reference data.

Four rules govern this module, and they are the reason verification is
reported separately from risk:

    not found      is not the same as fraudulent
    found          is not the same as safe
    blacklisted    is strong evidence of harm
    near match     is possible impersonation, never a pass

Registry data here is simulated. Absence from it proves nothing about the
real world, and the interface must say so.
"""

from __future__ import annotations

import csv
import logging
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.config import get_settings
from src.core.schemas import (
    EntityType,
    Posting,
    VerificationResult,
    VerificationStatus,
)
from src.db.models import RegistryRecord

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RegistryEntry:
    entity_id: str
    name: str
    normalised: str      # suffixes stripped
    basic: str           # suffixes retained
    status: str          # active | dormant | expired | revoked
    entity_type: EntityType
    licence_status: str = ""


@dataclass(frozen=True)
class BlacklistEntry:
    value: str
    normalised: str
    kind: str            # name | email | phone | domain
    reason: str


_companies: list[RegistryEntry] = []
_agencies: list[RegistryEntry] = []
_blacklist: list[BlacklistEntry] = []
_loaded = False

# Legal form suffixes are stripped before comparison so that
# "Global Talent Ltd" and "Global Talent Limited" match.
_SUFFIXES = re.compile(
    r"\b(ltd|limited|plc|llc|inc|incorporated|co|company|group|holdings|"
    r"enterprises|agency|agencies|recruitment|consultants?|services|"
    r"solutions|international|kenya|k)\b",
    re.IGNORECASE,
)


def basic_normalise(name: str | None) -> str:
    """Lowercase, strip punctuation, collapse whitespace. Suffixes retained."""
    if not name:
        return ""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", name.lower())).strip()


def normalise(name: str | None) -> str:
    """As above, but with legal and industry suffixes removed.

    Lets "Global Talent Ltd" match "Global Talent Limited".
    """
    if not name:
        return ""
    return re.sub(r"\s+", " ", _SUFFIXES.sub(" ", basic_normalise(name))).strip()


def _read_csv(path: Path, entity_type: EntityType) -> list[RegistryEntry]:
    if not path.exists():
        log.warning("Registry file missing: %s", path)
        return []

    entries: list[RegistryEntry] = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            name = (
                row.get("company_name")
                or row.get("agency_name")
                or row.get("name")
                or ""
            ).strip()
            if not name:
                continue
            entries.append(
                RegistryEntry(
                    entity_id=(
                        row.get("company_id")
                        or row.get("agency_id")
                        or row.get("id")
                        or ""
                    ),
                    name=name,
                    normalised=normalise(name),
                    basic=basic_normalise(name),
                    status=(row.get("status") or "active").strip().lower(),
                    entity_type=entity_type,
                    licence_status=(row.get("licence_status") or "").lower(),
                )
            )
    log.info("Loaded %d entries from %s", len(entries), path.name)
    return entries


def _read_blacklist(path: Path) -> list[BlacklistEntry]:
    if not path.exists():
        log.warning("Blacklist file missing: %s", path)
        return []

    entries: list[BlacklistEntry] = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            value = (row.get("value") or row.get("name") or "").strip()
            if not value:
                continue
            kind = (row.get("kind") or "name").strip().lower()
            entries.append(
                BlacklistEntry(
                    value=value,
                    normalised=(
                        normalise(value) if kind == "name" else value.lower()
                    ),
                    kind=kind,
                    reason=(row.get("reason") or "Listed by regulator").strip(),
                )
            )
    return entries


def load(force: bool = False) -> None:
    """Load registry seed data, optionally replacing in-memory records."""
    global _companies, _agencies, _blacklist, _loaded

    if _loaded and not force:
        return

    settings = get_settings()

    _companies = _read_csv(
        settings.company_registry_csv,
        EntityType.COMPANY,
    )
    _agencies = _read_csv(
        settings.agency_registry_csv,
        EntityType.AGENCY,
    )
    _blacklist = _read_blacklist(
        settings.blacklist_csv,
    )
    _loaded = True


def reload_from_database(session: Session) -> int:
    """Replace in-memory registry data with active database records."""
    global _companies, _agencies, _blacklist, _loaded

    records = session.scalars(
        select(RegistryRecord)
        .where(RegistryRecord.is_active.is_(True))
        .order_by(
            RegistryRecord.category.asc(),
            RegistryRecord.name.asc(),
        )
    ).all()

    companies: list[RegistryEntry] = []
    agencies: list[RegistryEntry] = []
    blacklist: list[BlacklistEntry] = []

    for record in records:
        if record.category == "company":
            companies.append(
                RegistryEntry(
                    entity_id=record.external_id or str(record.id),
                    name=record.name,
                    normalised=record.normalised_name,
                    basic=basic_normalise(record.name),
                    status=record.status,
                    entity_type=EntityType.COMPANY,
                )
            )
            continue

        if record.category == "agency":
            agencies.append(
                RegistryEntry(
                    entity_id=record.external_id or str(record.id),
                    name=record.name,
                    normalised=record.normalised_name,
                    basic=basic_normalise(record.name),
                    status=record.status,
                    entity_type=EntityType.AGENCY,
                    licence_status=record.licence_status or "",
                )
            )
            continue

        if record.category == "blacklist":
            kind = record.blacklist_kind or "name"
            blacklist.append(
                BlacklistEntry(
                    value=record.name,
                    normalised=(
                        record.normalised_name
                        if kind == "name"
                        else record.name.lower()
                    ),
                    kind=kind,
                    reason=(
                        record.blacklist_reason
                        or "Listed by regulator"
                    ),
                )
            )

    _companies = companies
    _agencies = agencies
    _blacklist = blacklist
    _loaded = True

    log.info(
        "Loaded %d companies, %d agencies, and %d blacklist "
        "entries from persistent registry storage.",
        len(_companies),
        len(_agencies),
        len(_blacklist),
    )

    return len(records)


def _similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, left, right).ratio()


def _best_match(
    name: str, haystack: list[RegistryEntry]
) -> tuple[RegistryEntry | None, float]:
    """Find the closest registry entry to the supplied name.

    Compares on two normalisations and keeps the better score. Suffix
    stripping helps "Ltd" match "Limited", but it misfires when a scammer
    misspells the suffix itself, as in "Recruitmnt Agancy". Scoring both
    forms catches the impersonation case that stripping alone would miss.
    """
    stripped = normalise(name)
    basic = basic_normalise(name)
    if not basic or not haystack:
        return None, 0.0

    best, score = None, 0.0
    for entry in haystack:
        ratio = max(
            _similarity(stripped, entry.normalised),
            _similarity(basic, entry.basic),
        )
        if ratio > score:
            best, score = entry, ratio
    return best, score


def _check_blacklist(posting: Posting, name: str) -> BlacklistEntry | None:
    normalised = normalise(name)
    email = (posting.contact_email or "").lower()
    phone = re.sub(r"[^0-9]", "", posting.contact_phone or "")

    for entry in _blacklist:
        if entry.kind == "name" and normalised and entry.normalised == normalised:
            return entry
        if entry.kind == "email" and email and entry.normalised == email:
            return entry
        if entry.kind == "domain" and email.endswith("@" + entry.normalised):
            return entry
        if entry.kind == "phone" and phone and phone.endswith(
            re.sub(r"[^0-9]", "", entry.normalised)[-9:]
        ):
            return entry
    return None


def verify(posting: Posting) -> VerificationResult:
    """Resolve the posting's named entity against the applicable registry."""
    load()

    name = posting.entity_name()
    entity_type = posting.entity_type

    # No named entity at all. Not an accusation, but nothing to verify either.
    if not name:
        return VerificationResult(
            status=VerificationStatus.NOT_APPLICABLE,
            entity_type=entity_type,
            entity_name=None,
        )

    blacklisted = _check_blacklist(posting, name)
    if blacklisted:
        return VerificationResult(
            status=VerificationStatus.BLACKLISTED,
            entity_type=entity_type,
            entity_name=name,
            matched_name=blacklisted.value,
            match_score=1.0,
            blacklist_reason=blacklisted.reason,
        )

    # Choose the registry that actually applies. An agency posting is checked
    # against the agency register; a direct employer against the companies
    # register. Where the type is unknown, try both and take the better match.
    if entity_type == EntityType.AGENCY:
        pool = _agencies
    elif entity_type == EntityType.COMPANY:
        pool = _companies
    else:
        pool = _agencies + _companies

    match, score = _best_match(name, pool)
    settings = get_settings()

    # Only an exact normalised match verifies an entity. This is deliberate.
    # A name that is close but not equal is the impersonation case, and
    # treating a 0.95 similarity as "verified" would let a scammer trading as
    # "Bright Future Recruitmnt Agancy" inherit the real agency's standing.
    if match and score >= 0.999:
        inactive = match.status not in {"active", ""} or (
            match.licence_status and match.licence_status != "active"
        )
        return VerificationResult(
            # A dormant, expired or revoked entry is not a clean verification.
            status=(
                VerificationStatus.UNVERIFIED
                if inactive
                else VerificationStatus.VERIFIED
            ),
            entity_type=match.entity_type,
            entity_name=name,
            matched_name=match.name,
            match_score=round(score, 3),
            registry_id=match.entity_id,
        )

    if match and score >= settings.impersonation_threshold:
        # Close but not equal: a possible attempt to trade on a registered
        # organisation's reputation with a near miss name.
        return VerificationResult(
            status=VerificationStatus.POSSIBLE_IMPERSONATION,
            entity_type=match.entity_type,
            entity_name=name,
            matched_name=match.name,
            match_score=round(score, 3),
            registry_id=match.entity_id,
        )

    return VerificationResult(
        status=VerificationStatus.UNVERIFIED,
        entity_type=entity_type,
        entity_name=name,
        match_score=round(score, 3) if match else 0.0,
    )
