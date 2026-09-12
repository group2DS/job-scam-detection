from datetime import datetime
from typing import Any, Dict


RISK_LABELS = {
    "lower_risk": "Lower risk",
    "suspicious": "Suspicious",
    "high_risk": "High risk",
}

VERIFICATION_LABELS = {
    "verified": "Verified",
    "unverified": "Unverified",
    "blacklisted": "Blacklisted",
    "possible_impersonation": "Possible impersonation",
    "not_applicable": "Not applicable",
}

REVIEW_STATUS_LABELS = {
    "open": "Open",
    "resolved": "Resolved",
    "pending": "Pending",
    "under_review": "Under review",
}

OUTCOME_LABELS = {
    "confirmed_legitimate": "Confirmed legitimate",
    "confirmed_scam": "Confirmed scam",
    "needs_more_evidence": "Needs more evidence",
    "duplicate_report": "Duplicate report",
}

RISK_COLORS = {
    "lower_risk": "#15803d",
    "suspicious": "#b45309",
    "high_risk": "#b91c1c",
}

VERIFICATION_COLORS = {
    "verified": "#15803d",
    "unverified": "#b45309",
    "blacklisted": "#b91c1c",
    "possible_impersonation": "#b45309",
    "not_applicable": "#64748b",
}

STATUS_COLORS = {
    "open": "#2563eb",
    "resolved": "#15803d",
    "pending": "#64748b",
    "under_review": "#7c3aed",
}


def display_value(value: Any, fallback: str = "Not provided") -> str:
    if value is None:
        return fallback

    if isinstance(value, str):
        cleaned_value = value.strip()

        if not cleaned_value:
            return fallback

        if cleaned_value.lower() in {
            "none",
            "null",
            "nan",
            "n/a",
        }:
            return fallback

        return cleaned_value

    return str(value)


def format_risk_level(value: Any) -> str:
    key = display_value(value, "").lower()
    return RISK_LABELS.get(key, display_value(value))


def format_verification_status(value: Any) -> str:
    key = display_value(value, "").lower()
    return VERIFICATION_LABELS.get(key, display_value(value))


def format_review_status(value: Any) -> str:
    key = display_value(value, "").lower()
    return REVIEW_STATUS_LABELS.get(key, display_value(value))


def format_outcome(value: Any) -> str:
    if value is None:
        return "No decision recorded"

    key = display_value(value, "").lower()
    return OUTCOME_LABELS.get(key, display_value(value))


def format_probability(value: Any) -> str:
    if value is None:
        return "Not provided"

    try:
        probability = float(value)
    except (TypeError, ValueError):
        return "Not provided"

    if probability < 0:
        probability = 0

    if probability > 1:
        probability = 1

    return "{:.1f}%".format(probability * 100)


def format_boolean(value: Any) -> str:
    if value is True:
        return "Yes"

    if value is False:
        return "No"

    return "Not provided"


def format_datetime(value: Any) -> str:
    if value is None:
        return "Not provided"

    raw_value = str(value).strip()

    if not raw_value:
        return "Not provided"

    try:
        parsed_value = datetime.fromisoformat(
            raw_value.replace("Z", "+00:00")
        )

        return parsed_value.strftime("%d %b %Y, %H:%M")
    except ValueError:
        return raw_value


def risk_color(value: Any) -> str:
    key = display_value(value, "").lower()
    return RISK_COLORS.get(key, "#64748b")


def verification_color(value: Any) -> str:
    key = display_value(value, "").lower()
    return VERIFICATION_COLORS.get(key, "#64748b")


def status_color(value: Any) -> str:
    key = display_value(value, "").lower()
    return STATUS_COLORS.get(key, "#64748b")


def badge_html(label: str, color: str) -> str:
    return (
        '<span style="'
        "display:inline-block;"
        "padding:0.25rem 0.65rem;"
        "border-radius:999px;"
        "background-color:{color}18;"
        "color:{color};"
        "border:1px solid {color}55;"
        "font-size:0.82rem;"
        "font-weight:700;"
        '">{label}</span>'
    ).format(
        label=label,
        color=color,
    )


def risk_badge(value: Any) -> str:
    return badge_html(
        format_risk_level(value),
        risk_color(value),
    )


def verification_badge(value: Any) -> str:
    return badge_html(
        format_verification_status(value),
        verification_color(value),
    )


def status_badge(value: Any) -> str:
    return badge_html(
        format_review_status(value),
        status_color(value),
    )


def format_reason(reason: Any) -> Dict[str, str]:
    if not isinstance(reason, dict):
        return {
            "code": "reason",
            "text": display_value(reason),
            "source": "Not provided",
        }

    return {
        "code": display_value(reason.get("code"), "reason"),
        "text": display_value(reason.get("text")),
        "source": display_value(reason.get("source")),
    }