"""
Turn raw input into a normalised Posting.

Pasted text is the primary path because it always works, including for
listings circulated on social media and messaging apps where there is no
clean URL to fetch. URL extraction is best effort.

Extraction failure is never treated as evidence of fraud. If a page cannot be
read, or does not look like a job listing, the caller is asked to paste the
text instead.
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

# ---------------------------------------------------------------------------
# Sanity checking fetched pages
#
# A page that loads successfully is not necessarily a job listing. Sites that
# require a session commonly return a login wall or a consent page, and those
# contain more than enough text to pass a naive length check. Assessing one
# produces a confident looking verdict about a page the person never saw,
# which is worse than admitting the fetch did not work.
# ---------------------------------------------------------------------------

_WALL_MARKERS = re.compile(
    r"\b(sign in to continue|log in to continue|please (sign|log) in|"
    r"create an account to|join now to|enable javascript|"
    r"verify you are (a )?human|access denied|"
    r"unusual traffic|are you a robot|checking your browser|"
    r"accept (all )?cookies to continue|subscribe to (read|continue))\b",
    re.IGNORECASE,
)

# Vocabulary a genuine listing almost always contains somewhere.
_JOB_MARKERS = re.compile(
    r"\b(responsibilit(y|ies)|duties|qualification|requirements?|experience|"
    r"salary|remuneration|applicants?|candidates?|vacanc(y|ies)|"
    r"job\s+(description|title|type)|apply|applications?|"
    r"employment|position|recruit)\b",
    re.IGNORECASE,
)


def looks_like_listing(text: str) -> tuple[bool, str]:
    """Decide whether fetched text plausibly is a job listing.

    Returns (ok, reason). The reason is shown to the person who submitted the
    link, so it is written for them rather than for a developer.
    """
    stripped = (text or "").strip()

    if len(stripped) < 200:
        return False, "too little text could be read from that page"

    if _WALL_MARKERS.search(stripped[:2000]):
        return False, "that page requires a login or blocks automated access"

    # Needs at least two distinct pieces of job vocabulary. One is too easy to
    # hit by accident on a navigation menu.
    if len({m.group(0).lower() for m in _JOB_MARKERS.finditer(stripped)}) < 2:
        return False, "that page does not appear to contain a job listing"

    return True, ""


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


class FetchFailed(Exception):
    """Raised when a URL cannot be turned into a usable listing.

    Carries a message written for the person who submitted the link. This is a
    usability problem, never a fraud signal, and the wording must not imply
    otherwise.
    """


def from_url(url: str) -> Posting:
    """Fetch and parse a listing page.

    Raises FetchFailed when the page cannot be retrieved or does not look like
    a job listing, so the caller can ask for a paste instead.
    """
    try:
        import httpx
        from bs4 import BeautifulSoup
    except ImportError as exc:
        raise FetchFailed(
            "Reading links is unavailable. Please paste the job description."
        ) from exc

    try:
        response = httpx.get(
            url,
            timeout=10.0,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (compatible; JobScamCheck/0.1; "
                    "capstone project)"
                ),
                "Accept-Language": "en-GB,en;q=0.9",
            },
        )
        response.raise_for_status()
    except Exception as exc:
        log.info("Could not fetch %s: %s", url, exc)
        raise FetchFailed(
            "That page could not be opened. It may require a login, or block "
            "automated access. Please paste the job description instead."
        ) from exc

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "form"]):
        tag.decompose()

    text = re.sub(r"\n{3,}", "\n\n", soup.get_text("\n")).strip()

    ok, reason = looks_like_listing(text)
    if not ok:
        log.info("Rejected %s: %s", url, reason)
        raise FetchFailed(
            f"We could not read a job listing from that link, because "
            f"{reason}. Please paste the job description instead."
        )

    posting = from_text(text, source_url=url)
    if soup.title and soup.title.string:
        posting.title = soup.title.string.strip()[:200]
    return posting
