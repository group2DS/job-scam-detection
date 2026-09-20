"""
The decision layer.

This is where the system's central design commitment lives: content risk and
entity verification are computed independently and reported independently.
Neither silently overrides the other.

It is deliberately rule based rather than a second model. A panel can read
this file and check it. A stacked ensemble would be one more thing that
cannot be explained to the person whose savings are at stake.

Thresholds live in config so the tiers can be retuned from validation data
without retraining anything.
"""

from __future__ import annotations

from src.core.config import get_settings
from src.core.schemas import (
    ModelResult,
    Posting,
    Reason,
    RiskLevel,
    RuleHit,
    VerificationResult,
    VerificationStatus,
)

# Rule weight above which a single deterministic signal is strong enough to
# raise the floor on its own, regardless of what the classifier thought.
_STRONG_RULE = 0.30


def _blend(probability: float, hits: list[RuleHit]) -> float:
    """Nudge the model probability using deterministic signals.

    The model is trained on a foreign corpus and will not have learned Kenya
    specific overseas placement patterns. The rules cover that gap. The nudge
    is capped so rules can inform the score but never manufacture it.
    """
    if not hits:
        return probability

    nudge = min(sum(hit.weight for hit in hits) * 0.5, 0.35)
    return round(min(probability + nudge, 0.99), 4)


def _risk_from(score: float, hits: list[RuleHit]) -> RiskLevel:
    settings = get_settings()

    if score >= settings.high_risk_threshold:
        return RiskLevel.HIGH_RISK

    # Two or more strong signals should not be filed as lower risk even when
    # the classifier is relaxed, because those signals are the patterns that
    # cost people money most often.
    strong = [hit for hit in hits if hit.weight >= _STRONG_RULE]
    if len(strong) >= 2:
        return RiskLevel.HIGH_RISK
    if strong:
        return RiskLevel.SUSPICIOUS

    if score >= settings.suspicious_threshold:
        return RiskLevel.SUSPICIOUS
    return RiskLevel.LOWER_RISK


def _apply_verification(risk: RiskLevel, verification: VerificationResult) -> RiskLevel:
    """Let verification adjust the tier, in one direction only.

    Verification can raise risk. It can never lower it, because a registered
    entity is perfectly capable of publishing a fraudulent advertisement, and
    a scammer can impersonate one.
    """
    if verification.status == VerificationStatus.BLACKLISTED:
        return RiskLevel.HIGH_RISK

    if verification.status == VerificationStatus.POSSIBLE_IMPERSONATION:
        return (
            RiskLevel.HIGH_RISK
            if risk == RiskLevel.HIGH_RISK
            else RiskLevel.SUSPICIOUS
        )

    # An unverified entity turns an otherwise clean posting into a caution,
    # not an accusation. This is the case the whole two status design exists
    # to express, and it is the most common real outcome.
    if (
        verification.status == VerificationStatus.UNVERIFIED
        and risk == RiskLevel.LOWER_RISK
    ):
        return RiskLevel.SUSPICIOUS

    return risk


def _reasons(
    model: ModelResult,
    hits: list[RuleHit],
    verification: VerificationResult,
) -> list[Reason]:
    """Build the explanation list, strongest signal first."""
    reasons: list[Reason] = []

    if verification.status == VerificationStatus.BLACKLISTED:
        reasons.append(
            Reason(
                code="blacklisted",
                text=(
                    f"{verification.entity_name} appears on a blacklist. "
                    f"{verification.blacklist_reason}"
                ),
                source="registry",
            )
        )
    elif verification.status == VerificationStatus.POSSIBLE_IMPERSONATION:
        reasons.append(
            Reason(
                code="possible_impersonation",
                text=(
                    f"The name '{verification.entity_name}' closely resembles "
                    f"'{verification.matched_name}' without matching it, which "
                    "can indicate impersonation of a registered organisation."
                ),
                source="registry",
            )
        )
    elif verification.status == VerificationStatus.UNVERIFIED:
        label = (
            "recruitment agency"
            if verification.entity_type.value == "agency"
            else "employer"
        )
        reasons.append(
            Reason(
                code="not_in_registry",
                text=(
                    f"The {label} could not be found in the registry. This does "
                    "not by itself mean the listing is fraudulent, but it could "
                    "not be confirmed."
                ),
                source="registry",
            )
        )

    for hit in sorted(hits, key=lambda h: h.weight, reverse=True):
        reasons.append(Reason(code=hit.code, text=hit.label, source="rule"))

    if not hits and model.probability < get_settings().suspicious_threshold:
        reasons.append(
            Reason(
                code="no_content_signals",
                text="No common scam patterns were detected in the listing text.",
                source="model",
            )
        )
    elif not hits:
        reasons.append(
            Reason(
                code="model_flagged",
                text=(
                    "The automated content model rated this listing as having "
                    "elevated risk, though no specific rule pattern was matched."
                ),
                source="model",
            )
        )   

    return reasons


def _recommendation(risk: RiskLevel, verification: VerificationStatus) -> str:
    """Advisory wording. Never asserts a legal conclusion about an entity."""
    if verification == VerificationStatus.BLACKLISTED:
        return (
            "This organisation appears on a blacklist. Do not send money or "
            "personal documents. This listing has been referred for review."
        )

    if risk == RiskLevel.HIGH_RISK:
        return (
            "This listing shows several patterns commonly associated with "
            "recruitment fraud. Do not pay any fee or share personal documents. "
            "This listing has been referred for review."
        )

    if risk == RiskLevel.SUSPICIOUS:
        if verification == VerificationStatus.POSSIBLE_IMPERSONATION:
            return (
                "Confirm you are dealing with the organisation itself by "
                "contacting it through details you find independently, not "
                "details given in this listing."
            )
        return (
            "This listing does not show strong scam indicators, but the "
            "organisation could not be verified. Do not send money or personal "
            "documents until you have confirmed it independently."
        )

    return (
        "No strong scam indicators were found and the organisation was located "
        "in the registry. Continue to apply normal caution, and never pay a fee "
        "to be considered for a job."
    )


def _should_refer(risk: RiskLevel, verification: VerificationResult, overseas: bool) -> bool:
    """Decide whether this becomes a case in the government queue."""
    if risk in {RiskLevel.HIGH_RISK, RiskLevel.SUSPICIOUS}:
        return True
    if verification.status in {
        VerificationStatus.BLACKLISTED,
        VerificationStatus.POSSIBLE_IMPERSONATION,
        VerificationStatus.UNVERIFIED,
    }:
        return True
    # Overseas placements carry the highest potential harm, so an unverified
    # overseas listing is escalated even when the text reads cleanly.
    return overseas and verification.status != VerificationStatus.VERIFIED


def combine(
    posting: Posting,
    model: ModelResult,
    hits: list[RuleHit],
    verification: VerificationResult,
    overseas: bool = False,
) -> tuple[RiskLevel, list[Reason], str, bool, float]:
    """Produce the final assessment.

    Returns risk level, reasons, recommendation, referral flag, blended score.
    """
    score = _blend(model.probability, hits)
    risk = _apply_verification(_risk_from(score, hits), verification)
    reasons = _reasons(model, hits, verification)
    recommendation = _recommendation(risk, verification.status)
    refer = _should_refer(risk, verification, overseas)
    return risk, reasons, recommendation, refer, score
