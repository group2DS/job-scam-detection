"""
Turn raw input into a normalised Posting.

Pasted text is the primary path because it always works, including for
listings circulated on social media and messaging apps where there is no
clean URL to fetch. URL extraction is best effort.

Extraction failure is never treated as evidence of fraud. If a URL cannot be
parsed the caller is asked to paste the text instead.
"""

from __future__ import annotations

import logging
import re

from src.core.schemas import EntityType, Posting

log = logging.getLogger(__name__)

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_PHONE = re.compile(r"(?:\+?254|0)\s?7\d{2}[\s-]?\d{3}[\s-]?\d{3}")
_SALARY = re.compile(
    r"(?:ksh?s?|kes|usd|\$)\s?[\d,]+(?:\s?(?:-|to)\s?(?:ksh?s?|kes)?\s?[\d,]+)?",
    re.IGNORECASE,
)

# Words that indicate the advertiser is an intermediary rather than the
# employer. This decides which registry the verification stage consults.
_AGENCY_HINT = re.compile(
    r"\b(recruit(ment|er|ing)?|agency|agencies|manpower|placement|"
    r"staffing|labour\s+export|employment\s+bureau)\b",
    re.IGNORECASE,
)

_OVERSEAS = re.compile(
    r"\b(qatar|dubai|uae|united\s+arab\s+emirates|saudi|riyadh|kuwait|oman|"
    r"bahrain|lebanon|jordan|cyprus|poland|romania|malta|canada|"
    r"abroad|overseas|gulf)\b",
    re.IGNORECASE,
)

_LABELLED_FIELD = re.compile(
    r"^\s*(title|position|role|company|employer|agency|location|salary|"
    r"contact|email|phone)\s*[:\-]\s*(.+)$",
    re.IGNORECASE | re.MULTILINE,
)


def from_text(text: str, source_url: str | None = None) -> Posting:
    """Parse a pasted job description into a Posting."""
    cleaned = text.strip()
    fields = {
        key.lower(): value.strip()
        for key, value in _LABELLED_FIELD.findall(cleaned)
    }

    title = fields.get("title") or fields.get("position") or fields.get("role")
    if not title:
        # Fall back to the first non trivial line, which is the title in most
        # pasted listings.
        for line in cleaned.splitlines():
            stripped = line.strip()
            if 5 < len(stripped) < 120:
                title = stripped
                break

    employer = fields.get("company") or fields.get("employer")
    agency = fields.get("agency")

    # Infer the advertiser type when it was not stated explicitly.
    entity_type = EntityType.UNKNOWN
    if agency:
        entity_type = EntityType.AGENCY
    elif employer and _AGENCY_HINT.search(employer):
        entity_type = EntityType.AGENCY
        agency, employer = employer, None
    elif employer:
        entity_type = EntityType.COMPANY
    elif _AGENCY_HINT.search(cleaned):
        entity_type = EntityType.AGENCY

    email_match = _EMAIL.search(cleaned)
    phone_match = _PHONE.search(cleaned)
    salary_match = _SALARY.search(cleaned)
    overseas_match = _OVERSEAS.search(cleaned)

    return Posting(
        title=title,
        description=cleaned,
        employer_name=employer,
        agency_name=agency,
        entity_type=entity_type,
        location=fields.get("location"),
        destination_country=overseas_match.group(0) if overseas_match else None,
        is_overseas=bool(overseas_match),
        salary_text=fields.get("salary")
        or (salary_match.group(0) if salary_match else None),
        contact_email=fields.get("email")
        or (email_match.group(0) if email_match else None),
        contact_phone=fields.get("phone")
        or (phone_match.group(0) if phone_match else None),
        source_url=source_url,
        raw_text=cleaned,
    )


def from_url(url: str) -> Posting | None:
    """Fetch and parse a listing page.

    Returns None when the page cannot be retrieved or yields too little text,
    so the caller can ask the user to paste instead. Deliberately tolerant:
    a failed fetch is a usability problem, not a fraud signal.
    """
    try:
        import httpx
        from bs4 import BeautifulSoup
    except ImportError:
        log.warning("httpx or beautifulsoup4 not installed; URL path disabled.")
        return None

    try:
        response = httpx.get(
            url,
            timeout=10.0,
            follow_redirects=True,
            headers={"User-Agent": "JobScamDetection/0.1 (capstone project)"},
        )
        response.raise_for_status()
    except Exception as exc:
        log.info("Could not fetch %s: %s", url, exc)
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    text = re.sub(r"\n{3,}", "\n\n", soup.get_text("\n")).strip()
    if len(text) < 100:
        return None

    posting = from_text(text, source_url=url)
    if soup.title and soup.title.string:
        posting.title = soup.title.string.strip()[:200]
    return posting
