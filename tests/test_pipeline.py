"""
Pipeline tests.

These cover the decision logic, which is the part of the system that must be
defensible. Each test encodes one of the four verification rules from the
architecture document.
"""

import pytest

from src.core.schemas import EntityType, RiskLevel, VerificationStatus
from src.decision import layer
from src.ingestion import extractor
from src.models import classifier
from src.rules import engine
from src.verification import registry


def assess(text: str):
    """Run the full pipeline on pasted text, bypassing the API."""
    posting = extractor.from_text(text)
    model = classifier.predict(posting.model_text() or posting.raw_text)
    hits = engine.evaluate(posting)
    verification = registry.verify(posting)
    overseas = engine.looks_overseas(posting)
    risk, reasons, rec, refer, score = layer.combine(
        posting, model, hits, verification, overseas
    )
    return posting, verification, risk, reasons, refer, score


# --------------------------------------------------------------------------
# Extraction
# --------------------------------------------------------------------------


def test_labelled_fields_are_parsed():
    posting = extractor.from_text(
        "Title: Warehouse Assistant\n"
        "Company: Twiga Foods Limited\n"
        "Location: Nairobi\n"
        "Email: hr@twiga.co.ke\n"
        "Duties include stock handling."
    )
    assert posting.title == "Warehouse Assistant"
    assert posting.employer_name == "Twiga Foods Limited"
    assert posting.contact_email == "hr@twiga.co.ke"
    assert posting.entity_type == EntityType.COMPANY


def test_agency_is_distinguished_from_employer():
    """A direct employer must not be checked against the agency register."""
    posting = extractor.from_text(
        "Title: Hotel Staff\nCompany: Skyline Manpower Services\nOverseas role."
    )
    assert posting.entity_type == EntityType.AGENCY
    assert posting.agency_name == "Skyline Manpower Services"


def test_overseas_is_detected():
    posting = extractor.from_text("Hotel Staff Required in Qatar. Apply now.")
    assert posting.is_overseas


# --------------------------------------------------------------------------
# Rules
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,code",
    [
        ("A registration fee of KES 3000 is required.", "upfront_fee"),
        ("Candidates must pay visa fees before travel.", "travel_fee"),
        ("Send the amount via Mpesa to confirm.", "mobile_money"),
        ("Your passport will be retained by the employer.", "passport_retention"),
        ("The contract will be signed on arrival.", "contract_on_arrival"),
        ("Earn very high income working from home.", "unrealistic_income"),
    ],
)
def test_rule_fires(text, code):
    posting = extractor.from_text(text)
    assert code in {hit.code for hit in engine.evaluate(posting)}


def test_clean_posting_fires_no_strong_rules():
    posting = extractor.from_text(
        "Title: Accountant\nCompany: Naivas Limited\n"
        "We seek a qualified accountant with CPA certification and three "
        "years of experience in retail. Applications close on 30 September."
    )
    strong = [h for h in engine.evaluate(posting) if h.weight >= 0.30]
    assert strong == []


# --------------------------------------------------------------------------
# Verification, the four rules
# --------------------------------------------------------------------------


def test_registered_company_verifies():
    posting = extractor.from_text("Title: Analyst\nCompany: Safaricom PLC\nNairobi.")
    assert registry.verify(posting).status == VerificationStatus.VERIFIED


def test_legal_suffix_does_not_block_match():
    posting = extractor.from_text("Title: Driver\nCompany: Naivas Ltd\nNairobi.")
    assert registry.verify(posting).status == VerificationStatus.VERIFIED


def test_unknown_entity_is_unverified_not_fraud():
    """Not found is not the same as fraudulent."""
    posting = extractor.from_text(
        "Title: Office Assistant\nCompany: Mwangi Hardware Supplies\n"
        "We need an assistant for our shop in Nakuru. Normal duties apply."
    )
    result = registry.verify(posting)
    assert result.status == VerificationStatus.UNVERIFIED


def test_blacklisted_entity_is_flagged():
    posting = extractor.from_text(
        "Title: Hotel Staff\nAgency: Swift Resources Agency\nQatar placement."
    )
    result = registry.verify(posting)
    assert result.status == VerificationStatus.BLACKLISTED
    assert result.blacklist_reason


def test_near_miss_name_is_impersonation():
    """A close but inexact match is a warning, never a pass."""
    posting = extractor.from_text(
        "Title: Hotel Staff\nAgency: Bright Future Recruitmnt Agancy\nQatar."
    )
    result = registry.verify(posting)
    assert result.status == VerificationStatus.POSSIBLE_IMPERSONATION
    assert result.matched_name == "Bright Future Recruitment Agency"


def test_revoked_licence_does_not_verify():
    posting = extractor.from_text(
        "Title: Cleaner\nAgency: Horizon Labour Export Agency\nSaudi Arabia."
    )
    assert registry.verify(posting).status != VerificationStatus.VERIFIED


# --------------------------------------------------------------------------
# Decision layer
# --------------------------------------------------------------------------


def test_blacklist_forces_high_risk():
    _, verification, risk, _, refer, _ = assess(
        "Title: Hotel Staff\nAgency: Swift Resources Agency\n"
        "Good opportunity in Qatar for hospitality staff."
    )
    assert verification.status == VerificationStatus.BLACKLISTED
    assert risk == RiskLevel.HIGH_RISK
    assert refer


def test_clean_text_but_unverified_becomes_suspicious():
    """The case the two status design exists for."""
    _, verification, risk, reasons, refer, _ = assess(
        "Title: Office Assistant\nCompany: Mwangi Hardware Supplies\n"
        "We are looking for an office assistant in Nakuru. Duties include "
        "filing, reception and general administration. Applications close "
        "on 30 September. Interviews will be held at our premises."
    )
    assert verification.status == VerificationStatus.UNVERIFIED
    assert risk == RiskLevel.SUSPICIOUS
    assert any(r.code == "not_in_registry" for r in reasons)
    assert refer


def test_verified_company_clean_text_is_lower_risk():
    _, verification, risk, _, refer, _ = assess(
        "Title: Accountant\nCompany: Safaricom PLC\nLocation: Nairobi\n"
        "We seek a qualified accountant with CPA certification and three "
        "years of relevant experience. Interviews will be scheduled with "
        "shortlisted candidates."
    )
    assert verification.status == VerificationStatus.VERIFIED
    assert risk == RiskLevel.LOWER_RISK
    assert not refer


def test_verified_entity_cannot_launder_a_scam():
    """Found in a registry is not the same as safe."""
    _, verification, risk, _, _, _ = assess(
        "Title: Sales Agent\nCompany: Safaricom PLC\n"
        "Urgent hiring. Pay a registration fee of KES 5000 via Mpesa to "
        "secure your position. No interview required."
    )
    assert verification.status == VerificationStatus.VERIFIED
    assert risk == RiskLevel.HIGH_RISK


def test_two_strong_signals_escalate_regardless_of_model():
    _, _, risk, _, _, _ = assess(
        "Title: Driver\nCompany: Naivas Limited\n"
        "Pay a processing fee via Mpesa. Your passport will be retained."
    )
    assert risk == RiskLevel.HIGH_RISK


def test_reasons_are_always_present():
    for text in [
        "Title: Accountant\nCompany: Safaricom PLC\nQualified accountant needed.",
        "Pay a visa fee to travel to Dubai urgently.",
    ]:
        _, _, _, reasons, _, _ = assess(text)
        assert reasons, "every result must explain itself"


def test_probability_stays_in_range():
    _, _, _, _, _, score = assess(
        "Urgent! Pay registration fee via Mpesa. Passport retained. "
        "Earn very high income. No interview needed. Contract on arrival."
    )
    assert 0.0 <= score <= 1.0
