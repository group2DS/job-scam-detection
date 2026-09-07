"""
Deterministic scam signal detection.

These rules exist alongside the classifier, not inside it. Three reasons:

1. They are explainable. "An upfront visa fee was requested" is actionable
   in a way that "probability 0.71" is not.
2. They encode Kenya specific patterns that a model trained on a foreign
   corpus will not have learned, particularly overseas placement fraud.
3. They are auditable. A reviewer can check whether a rule fired correctly;
   they cannot audit a coefficient.

Weights are advisory nudges applied by the decision layer. They are not
probabilities and they do not sum to one.
"""

from __future__ import annotations

import re

from src.core.schemas import Posting, RuleHit

# Each rule: code, human label, regex, weight, category.
# Weights reflect how strongly the signal indicates fraud in isolation.
_RULES: list[tuple[str, str, str, float]] = [
    (
        "upfront_fee",
        "Upfront fee requested before employment",
        r"\b(registration|processing|application|placement|recruitment|"
        r"administration)\s+fee\b",
        0.35,
    ),
    (
        "travel_fee",
        "Payment requested for visa, medical or travel costs",
        r"\b(visa|medical|training|air\s?ticket|flight|passport)\s+"
        r"(fee|fees|charge|cost|payment)\b",
        0.35,
    ),
    (
        "mobile_money",
        "Payment requested to a mobile money number",
        r"\b(m-?pesa|mpesa|paybill|till\s+number|send\s+(money|cash))\b",
        0.30,
    ),
    (
        "pay_to_apply",
        "Payment required to apply or to secure the position",
        r"\b(pay|deposit|send)\b[^.]{0,40}\b(to\s+(apply|secure|confirm|"
        r"reserve|book))\b",
        0.35,
    ),
    (
        "passport_retention",
        "Employer retains the applicant's passport",
        r"\bpassport\b[^.]{0,40}\b(retain|retained|hold|held|surrender|"
        r"keep|kept|submit)\b",
        0.30,
    ),
    (
        "contract_on_arrival",
        "Contract only provided after arrival",
        r"\bcontract\b[^.]{0,40}\b(on|upon|after)\s+arrival\b",
        0.30,
    ),
    (
        "no_interview",
        "No interview or screening required",
        r"\bno\s+(interview|cv|resume|experience|qualification)"
        r"s?\s+(needed|required|necessary)\b",
        0.20,
    ),
    (
        "urgency",
        "Artificial urgency or limited availability",
        r"\b(urgent(ly)?|immediate(ly)?|limited\s+(slots|positions|"
        r"vacancies)|hurry|act\s+now|today\s+only)\b",
        0.10,
    ),
    (
        "unrealistic_income",
        "Unusually high or guaranteed income promised",
        r"\b(earn\s+(up\s+to\s+)?(very\s+)?high|unlimited\s+(income|"
        r"earning)|guaranteed\s+(income|salary|earning)|quick\s+money|"
        r"easy\s+money)\b",
        0.25,
    ),
    (
        "personal_email",
        "Free personal email address used for a corporate role",
        r"@(gmail|yahoo|hotmail|outlook|live|aol)\.(com|co\.ke)",
        0.15,
    ),
    (
        "whatsapp_only",
        "Application handled only through a messaging app",
        r"\b(whats\s?app|telegram|dm\s+(me|us))\b[^.]{0,30}\b(only|apply|"
        r"contact|inbox)\b",
        0.20,
    ),
    (
        "vague_role",
        "Role description lacks specific duties",
        r"\b(various\s+positions|different\s+posts|any\s+position|"
        r"multiple\s+vacancies)\b",
        0.15,
    ),
    (
        "government_claim",
        "Claims affiliation with a government programme",
        r"\b(government|ministry|county)\s+(approved|sponsored|backed|"
        r"programme|program)\b",
        0.20,
    ),
    (
        "personal_data_upfront",
        "Sensitive personal data requested before any interview",
        r"\b(id\s+(number|copy)|national\s+id|kra\s+pin|bank\s+(account|"
        r"details))\b[^.]{0,60}\b(send|submit|provide|share)\b",
        0.25,
    ),
]

_COMPILED = [
    (code, label, re.compile(pattern, re.IGNORECASE), weight)
    for code, label, pattern, weight in _RULES
]

# Overseas placement raises the stakes rather than the probability. It is
# recorded so the decision layer can route more cautiously, not to inflate risk.
_OVERSEAS_HINT = re.compile(
    r"\b(abroad|overseas|qatar|dubai|uae|saudi|kuwait|oman|bahrain|lebanon|"
    r"cyprus|poland|romania|canada\s+visa|gulf)\b",
    re.IGNORECASE,
)


def evaluate(posting: Posting) -> list[RuleHit]:
    """Run every rule against the posting and return the hits."""
    haystack = " ".join(
        part
        for part in [
            posting.title,
            posting.description,
            posting.raw_text,
            posting.contact_email,
        ]
        if part
    )

    hits: list[RuleHit] = []
    for code, label, pattern, weight in _COMPILED:
        match = pattern.search(haystack)
        if match:
            hits.append(
                RuleHit(
                    code=code,
                    label=label,
                    weight=weight,
                    evidence=_snippet(haystack, match.start(), match.end()),
                )
            )
    return hits


def looks_overseas(posting: Posting) -> bool:
    """Heuristic flag for overseas placement, used for routing only."""
    if posting.is_overseas or posting.destination_country:
        return True
    haystack = " ".join(
        p for p in [posting.title, posting.description, posting.location] if p
    )
    return bool(_OVERSEAS_HINT.search(haystack))


def _snippet(text: str, start: int, end: int, window: int = 40) -> str:
    """Short quoted context so a reviewer can see why a rule fired."""
    left = max(0, start - window)
    right = min(len(text), end + window)
    fragment = text[left:right].replace("\n", " ").strip()
    return f"...{fragment}..." if left > 0 or right < len(text) else fragment
