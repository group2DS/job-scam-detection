"""
Ingestion sanity tests.

These cover the case that produced a misleading result in testing: a page
that loads successfully, returns plenty of text, and is not a job listing.
A login wall assessed as a posting gives someone a confident verdict about a
page they never saw.
"""

import pytest

from src.ingestion.extractor import looks_like_listing

# Trimmed from what LinkedIn returns to an unauthenticated request.
LOGIN_WALL = """
LinkedIn
Sign in to continue to LinkedIn
Email or phone
Password
Forgot password?
New to LinkedIn? Join now
By clicking Continue, you agree to the User Agreement, Privacy Policy and
Cookie Policy. LinkedIn is the world's largest professional network with
members in more than 200 countries and territories worldwide.
"""

CONSENT_PAGE = """
We value your privacy
We and our partners store and access information on a device, such as cookies
and process personal data. You may accept or manage your choices by clicking
below. Accept all cookies to continue to the site. Your choices will be
signalled to our partners and will not affect browsing data.
"""

BOT_CHECK = """
Checking your browser before accessing the site.
This process is automatic. Your browser will redirect shortly.
Please enable JavaScript and cookies to continue. Verify you are human by
completing the action below. Ray ID reference for this request is shown here.
"""

REAL_LISTING = """
Accountant
Safaricom PLC, Nairobi

Job description
We are looking for a qualified accountant to join our finance team.

Responsibilities
Preparing monthly management accounts, supporting the annual audit, and
maintaining supplier records.

Requirements
CPA certification and at least three years of relevant experience.

Salary: competitive. Applications close on 30 September. Shortlisted
candidates will be contacted for an interview.
"""

SPARSE_LISTING = """
Hotel Staff Required in Qatar

Accommodation and transport provided. Candidates should have at least one
year of experience in hotel service and hold a valid passport. Apply by
sending your details to the contact below. Interviews will be arranged for
shortlisted applicants next week in Nairobi.
"""


@pytest.mark.parametrize(
    "text,label",
    [
        (LOGIN_WALL, "login wall"),
        (CONSENT_PAGE, "cookie consent page"),
        (BOT_CHECK, "bot check"),
        ("Page not found.", "short error page"),
        ("", "empty response"),
    ],
)
def test_non_listings_are_rejected(text, label):
    ok, reason = looks_like_listing(text)
    assert not ok, f"{label} was accepted as a job listing"
    assert reason, "a rejection must explain itself to the user"


@pytest.mark.parametrize(
    "text,label",
    [
        (REAL_LISTING, "full listing"),
        (SPARSE_LISTING, "sparse but genuine listing"),
    ],
)
def test_genuine_listings_are_accepted(text, label):
    ok, reason = looks_like_listing(text)
    assert ok, f"{label} was rejected: {reason}"

def test_short_genuine_listing_passes_upload_floor():
    text = (
        "Title: Hotel Staff\nAgency: Swift Resources Agency\nLocation: Qatar\n"
        "Pay a registration fee of KES 5000 via Mpesa to secure the position. "
        "Applicants should have experience in hotel service."
    )
    assert looks_like_listing(text, min_length=40)[0]
    assert not looks_like_listing(text)[0]   # rejected at the web page floor