"""Hakiki Hire Government Dashboard with authentication and access management."""

from __future__ import annotations

import os
import sys
from datetime import date, datetime, timezone
from html import escape
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
GOVERNMENT_DIR = Path(__file__).resolve().parent
for import_path in (PROJECT_ROOT, GOVERNMENT_DIR):
    value = str(import_path)
    if value not in sys.path:
        sys.path.insert(0, value)

from src.core.schemas import ReviewOutcome

from analytics import (
    render_overview_analytics,
    render_report_analytics,
    render_report_summary,
)
from api_client import HakikiHireAPIClient, HakikiHireAPIError
from report_generator import generate_summary_report_pdf, report_filename

LOCAL_API_URL = "http://127.0.0.1:8000"
LIVE_API_URL = "https://job-scam-api-vbc3.onrender.com"

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
REVIEW_LABELS = {"open": "Open", "resolved": "Resolved"}
OUTCOME_LABELS = {
    "confirmed_legitimate": "Confirmed legitimate",
    "confirmed_scam": "Confirmed scam",
    "needs_more_evidence": "Needs more evidence",
    "duplicate": "Duplicate report",
}

st.set_page_config(
    page_title="Hakiki Hire Government Dashboard",
    page_icon="HH",
    layout="wide",
    initial_sidebar_state="expanded",
)


def display_value(value: Any, fallback: str = "Not provided") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    if not text or text.lower() in {"none", "null", "nan"}:
        return fallback
    return text


def format_risk(value: Any) -> str:
    return RISK_LABELS.get(value, display_value(value))


def format_verification(value: Any) -> str:
    return VERIFICATION_LABELS.get(value, display_value(value))


def format_review_status(value: Any) -> str:
    return REVIEW_LABELS.get(value, display_value(value))


def format_outcome(value: Any) -> str:
    if value is None:
        return "No decision recorded"
    return OUTCOME_LABELS.get(
        value,
        str(value).replace("_", " ").strip().capitalize(),
    )


def format_probability(value: Any) -> str:
    try:
        probability = max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return "Not provided"
    return "{:.1f}%".format(probability * 100)


def format_datetime(value: Any) -> str:
    if value is None:
        return "Not provided"
    text = str(value).strip()
    if not text:
        return "Not provided"
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.strftime("%d %b %Y %H:%M")
    except ValueError:
        return text


def format_boolean(value: Any) -> str:
    if value is True:
        return "Yes"
    if value is False:
        return "No"
    return "Not provided"


def badge_html(label: str, color: str) -> str:
    return (
        '<span class="badge" style="color:{0};border-color:{0};">{1}</span>'
    ).format(color, escape(label))


def risk_badge(value: Any) -> str:
    colors = {
        "lower_risk": "#15803d",
        "suspicious": "#b45309",
        "high_risk": "#b91c1c",
    }
    return badge_html(format_risk(value), colors.get(value, "#475569"))


def verification_badge(value: Any) -> str:
    colors = {
        "verified": "#15803d",
        "unverified": "#b45309",
        "blacklisted": "#b91c1c",
        "possible_impersonation": "#b45309",
        "not_applicable": "#475569",
    }
    return badge_html(
        format_verification(value),
        colors.get(value, "#475569"),
    )


def status_badge(value: Any) -> str:
    colors = {"open": "#075985", "resolved": "#15803d"}
    return badge_html(
        format_review_status(value),
        colors.get(value, "#475569"),
    )


def apply_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --navy:#071f33; --blue:#0a3a59; --cyan:#74d4ff;
            --page:#f4f7fb; --text:#10233b; --body:#334155;
            --muted:#64748b; --border:#dbe3ec;
        }
        .stApp { background:var(--page); }
        .block-container { max-width:1400px; padding-top:.8rem; padding-bottom:3rem; }
        div[data-testid="stMainBlockContainer"] h1,
        div[data-testid="stMainBlockContainer"] h2,
        div[data-testid="stMainBlockContainer"] h3,
        div[data-testid="stMainBlockContainer"] h4 {
            color:var(--text)!important; -webkit-text-fill-color:var(--text)!important;
        }
        div[data-testid="stMainBlockContainer"] p,
        div[data-testid="stMainBlockContainer"] label,
        div[data-testid="stMainBlockContainer"] li {
            color:var(--body)!important; -webkit-text-fill-color:var(--body)!important;
        }
        .hero { position:relative; overflow:hidden; display:flex; gap:1rem;
            min-height:195px; padding:1.9rem 2rem; margin:-.8rem 0 1.6rem;
            background:linear-gradient(135deg,var(--navy),var(--blue));
            border-radius:0 0 18px 18px; box-shadow:0 18px 34px rgba(15,23,42,.22); }
        .hero-mark,.login-mark { display:flex; align-items:center; justify-content:center;
            color:#fff!important; -webkit-text-fill-color:#fff!important;
            border:1px solid rgba(255,255,255,.42); background:rgba(255,255,255,.08);
            border-radius:14px; font-weight:900; }
        .hero-mark { width:46px; height:46px; flex:0 0 46px; margin-top:1rem; }
        .hero-title { color:#fff!important; -webkit-text-fill-color:#fff!important;
            font-size:2rem; font-weight:800; line-height:1.15; margin-top:.45rem; }
        .hero-eyebrow { color:var(--cyan)!important; -webkit-text-fill-color:var(--cyan)!important;
            font-size:.72rem; font-weight:800; letter-spacing:.14em; text-transform:uppercase; }
        .hero-copy { max-width:780px; color:#dbeafe!important;
            -webkit-text-fill-color:#dbeafe!important; line-height:1.65; margin-top:.8rem; }
        .hero-pill { display:inline-block; color:#fff!important; -webkit-text-fill-color:#fff!important;
            border:1px solid rgba(255,255,255,.4); border-radius:999px;
            margin-top:.9rem; padding:.35rem .7rem; font-size:.72rem; }
        .login-heading { text-align:center; margin:1rem 0 1.7rem; }
        .login-heading-title { color:var(--navy)!important; -webkit-text-fill-color:var(--navy)!important;
            font-size:1.8rem; font-weight:800; }
        .login-heading-copy { color:var(--muted)!important; -webkit-text-fill-color:var(--muted)!important; }
        .login-panel { min-height:455px; padding:3rem; background:linear-gradient(145deg,var(--navy),var(--blue));
            border-radius:22px; box-shadow:0 22px 50px rgba(15,23,42,.18); }
        .login-mark { width:58px; height:58px; }
        .login-kicker { margin-top:2rem; color:var(--cyan)!important;
            -webkit-text-fill-color:var(--cyan)!important; font-size:.72rem;
            font-weight:800; letter-spacing:.14em; text-transform:uppercase; }
        .login-title { color:#fff!important; -webkit-text-fill-color:#fff!important;
            font-size:2.35rem; font-weight:800; line-height:1.14; margin-top:.65rem; }
        .login-copy { color:#dbeafe!important; -webkit-text-fill-color:#dbeafe!important;
            line-height:1.7; margin-top:1rem; max-width:420px; }
        .login-chip { display:inline-block; margin-top:2rem; padding:.45rem .8rem;
            color:#bae6fd!important; -webkit-text-fill-color:#bae6fd!important;
            border:1px solid rgba(255,255,255,.22); border-radius:999px;
            background:rgba(255,255,255,.07); font-size:.76rem; }
        .badge { display:inline-block; background:#fff; border:1px solid;
            border-radius:999px; font-size:.8rem; font-weight:700;
            margin-right:.3rem; padding:.22rem .65rem; }
        .case-card { background:#fff; border:1px solid var(--border); border-radius:14px;
            box-shadow:0 4px 14px rgba(15,23,42,.05); margin-bottom:.65rem; padding:1.1rem; }
        .case-card h3 { color:#0f172a!important; margin:0 0 .3rem; }
        .case-meta { color:var(--muted)!important; font-size:.84rem; margin-top:.6rem; }
        .empty-state { background:#fff; border:1px dashed #94a3b8; border-radius:14px;
            padding:2rem; text-align:center; }
        div[data-testid="stMetric"],div[data-testid="stForm"],
        div[data-testid="stVerticalBlockBorderWrapper"] { background:#fff!important;
            border:1px solid var(--border)!important; border-radius:14px!important; }
        div[data-testid="stTextInput"] input,div[data-testid="stTextArea"] textarea,
        div[data-baseweb="select"]>div { background:#fff!important; color:#0f172a!important;
            -webkit-text-fill-color:#0f172a!important; border-color:#cbd5e1!important; }
        div[data-testid="stFormSubmitButton"] button { min-height:46px!important; color:#fff!important;
            background:linear-gradient(135deg,#075985,#0a6a96)!important; border:none!important; }
        div[data-testid="stFormSubmitButton"] button p { color:#fff!important; -webkit-text-fill-color:#fff!important; }
        section[data-testid="stSidebar"],section[data-testid="stSidebar"]>div,
        section[data-testid="stSidebar"] div[data-testid="stSidebarContent"] {
            background:linear-gradient(180deg,var(--navy),var(--blue))!important; }
        section[data-testid="stSidebar"] h1,section[data-testid="stSidebar"] h2,
        section[data-testid="stSidebar"] h3,section[data-testid="stSidebar"] p,
        section[data-testid="stSidebar"] label,section[data-testid="stSidebar"] span {
            color:#fff!important; -webkit-text-fill-color:#fff!important; }
        .reviewer-panel { background:rgba(255,255,255,.08); border:1px solid rgba(255,255,255,.18);
            border-radius:12px; margin:.8rem 0 1rem; padding:.85rem; }
        .reviewer-name { color:#fff!important; -webkit-text-fill-color:#fff!important; font-weight:750; }
        .reviewer-role { color:#bae6fd!important; -webkit-text-fill-color:#bae6fd!important;
            font-size:.76rem; text-transform:capitalize; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def initialise_state() -> None:
    defaults = {
        "selected_case_id": None,
        "api_environment": "Local API",
        "access_token": None,
        "reviewer_profile": None,
        "navigation_page": "Overview",
        "login_error": None,
        "filter_risk": "All",
        "filter_verification": "All",
        "filter_status": "All",
        "filter_market": "All",
        "filter_country": "All",
        "filter_date_from": None,
        "filter_date_to": None,
        "filter_limit": 200,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def create_client() -> HakikiHireAPIClient:
    live = st.session_state.get("api_environment") == "Live API"
    return HakikiHireAPIClient(
        base_url=LIVE_API_URL if live else LOCAL_API_URL,
        timeout=45 if live else 30,
        access_token=st.session_state.get("access_token"),
    )


def clear_authentication() -> None:
    st.session_state.access_token = None
    st.session_state.reviewer_profile = None
    st.session_state.selected_case_id = None
    st.session_state.pending_navigation = "Overview"


def handle_api_error(error: HakikiHireAPIError) -> None:
    if error.status_code == 401:
        clear_authentication()
        st.session_state.login_error = "Your session expired. Please sign in again."
        st.rerun()
    st.error(error.message)


def hide_sidebar_for_login() -> None:
    st.markdown(
        """
        <style>
        section[data-testid="stSidebar"],button[data-testid="stSidebarCollapsedControl"],
        div[data-testid="collapsedControl"] { display:none!important; }
        .block-container { max-width:1120px!important; padding-top:1.4rem!important; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_login() -> None:
    hide_sidebar_for_login()
    st.markdown(
        """
        <div class="login-heading">
            <div class="login-heading-title">Hakiki Hire Government Portal</div>
            <div class="login-heading-copy">Protected access for authorised government reviewers</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    brand_column, form_column = st.columns([1.08, .92], gap="large")
    with brand_column:
        st.markdown(
            """
            <div class="login-panel">
                <div class="login-mark">HH</div>
                <div class="login-kicker">Government Review Portal</div>
                <div class="login-title">Hakiki Hire<br>Reviewer Access</div>
                <div class="login-copy">Review referred job postings, examine risk and verification evidence,
                and record accountable decisions through the protected portal.</div>
                <div class="login-chip">Secure reviewer authentication</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with form_column:
        st.markdown("### Welcome back")
        st.caption("Sign in using an authorised reviewer or administrator account.")
        if st.session_state.get("login_error"):
            st.error(st.session_state.pop("login_error"))
        environment = st.selectbox(
            "API environment",
            ["Local API", "Live API"],
            key="login_environment",
        )
        st.session_state.api_environment = environment
        with st.form("reviewer_login_form"):
            username = st.text_input("Username", placeholder="Enter your username")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            submitted = st.form_submit_button("Sign in securely", type="primary", width="stretch")
        if not submitted:
            return
        if not username.strip() or not password:
            st.error("Enter both username and password.")
            return
        client = create_client()
        try:
            result = client.login(username, password)
            st.session_state.access_token = client.access_token
            st.session_state.reviewer_profile = result["reviewer"]
            st.rerun()
        except (ValueError, HakikiHireAPIError) as error:
            st.error(getattr(error, "message", str(error)))


def render_header() -> None:
    environment = "LIVE API" if st.session_state.api_environment == "Live API" else "LOCAL API"
    st.markdown(
        """
        <div class="hero">
            <div class="hero-mark">HH</div>
            <div>
                <div class="hero-eyebrow">Government Review Portal</div>
                <div class="hero-title">Hakiki Hire Government Dashboard</div>
                <div class="hero-copy">Review referred job postings, examine risk and verification evidence,
                and record accountable reviewer decisions.</div>
                <div class="hero-pill">{environment}</div>
            </div>
        </div>
        """.format(environment=environment),
        unsafe_allow_html=True,
    )


def reset_filters() -> None:
    st.session_state.filter_risk = "All"
    st.session_state.filter_verification = "All"
    st.session_state.filter_status = "All"
    st.session_state.filter_market = "All"
    st.session_state.filter_country = "All"
    st.session_state.filter_date_from = None
    st.session_state.filter_date_to = None
    st.session_state.filter_limit = 200


def render_sidebar(client: HakikiHireAPIClient) -> Tuple[str, Dict[str, Any]]:
    reviewer = st.session_state.get("reviewer_profile") or {}
    name = display_value(
        reviewer.get("display_name") or reviewer.get("username"),
        "Authenticated reviewer",
    )
    role = display_value(reviewer.get("role"), "reviewer")
    st.sidebar.title("Hakiki Hire")
    st.sidebar.markdown(
        '<div class="reviewer-panel"><div class="reviewer-name">{}</div>'
        '<div class="reviewer-role">{}</div></div>'.format(escape(name), escape(role)),
        unsafe_allow_html=True,
    )

    pages = ["Overview", "Review queue", "Reports"]
    if role == "admin":
        pages.append("Access management")
    if st.session_state.navigation_page not in pages:
        st.session_state.pending_navigation = "Overview"
    page = st.sidebar.radio("Navigation", pages, key="navigation_page")

    if st.sidebar.button("Sign out", width="stretch"):
        client.logout()
        clear_authentication()
        st.rerun()

    try:
        countries = client.get_destination_countries()
    except HakikiHireAPIError as error:
        handle_api_error(error)
        countries = []

    valid_countries = ["All", *countries]
    if st.session_state.filter_country not in valid_countries:
        st.session_state.filter_country = "All"

    st.sidebar.divider()
    st.sidebar.subheader("Queue filters")
    risk = st.sidebar.selectbox(
        "Risk level",
        ["All", "Lower risk", "Suspicious", "High risk"],
        key="filter_risk",
    )
    verification = st.sidebar.selectbox(
        "Verification status",
        ["All", "Verified", "Unverified", "Blacklisted", "Possible impersonation", "Not applicable"],
        key="filter_verification",
    )
    review = st.sidebar.selectbox(
        "Review status",
        ["All", "Open", "Resolved"],
        key="filter_status",
    )
    market = st.sidebar.selectbox(
        "Market",
        ["All", "Local", "Overseas"],
        key="filter_market",
    )
    country = st.sidebar.selectbox(
        "Destination country",
        valid_countries,
        key="filter_country",
    )
    date_from = st.sidebar.date_input(
        "From date",
        value=st.session_state.filter_date_from,
        key="filter_date_from",
    )
    date_to = st.sidebar.date_input(
        "To date",
        value=st.session_state.filter_date_to,
        key="filter_date_to",
    )
    limit = st.sidebar.slider("Maximum cases", 1, 200, key="filter_limit")
    dates_invalid = bool(date_from and date_to and date_from > date_to)
    if dates_invalid:
        st.sidebar.error("From date must be on or before To date.")
    if st.sidebar.button("Refresh dashboard", width="stretch"):
        st.rerun()
    st.sidebar.button("Reset filters", on_click=reset_filters, width="stretch")

    return page, {
        "risk_level": {"All": None, "Lower risk": "lower_risk", "Suspicious": "suspicious", "High risk": "high_risk"}[risk],
        "verification_status": {
            "All": None, "Verified": "verified", "Unverified": "unverified",
            "Blacklisted": "blacklisted", "Possible impersonation": "possible_impersonation",
            "Not applicable": "not_applicable",
        }[verification],
        "review_status": {"All": None, "Open": "open", "Resolved": "resolved"}[review],
        "is_overseas": {"All": None, "Local": False, "Overseas": True}[market],
        "destination_country": None if country == "All" else country,
        "date_from": date_from.isoformat() if date_from else None,
        "date_to": date_to.isoformat() if date_to else None,
        "limit": limit,
        "dates_invalid": dates_invalid,
    }


def load_filtered_cases(client: HakikiHireAPIClient, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
    if filters.get("dates_invalid"):
        return []
    arguments = {key: value for key, value in filters.items() if key != "dates_invalid"}
    try:
        return client.get_cases(**arguments)
    except (ValueError, HakikiHireAPIError) as error:
        if isinstance(error, HakikiHireAPIError):
            handle_api_error(error)
        else:
            st.error(str(error))
        return []


def render_summary(cases: List[Dict[str, Any]]) -> None:
    columns = st.columns(5)
    columns[0].metric("Cases in view", len(cases))
    columns[1].metric("Open", sum(case.get("review_status") == "open" for case in cases))
    columns[2].metric("High risk", sum(case.get("risk_level") == "high_risk" for case in cases))
    columns[3].metric("Blacklisted", sum(case.get("verification_status") == "blacklisted" for case in cases))
    columns[4].metric("Resolved", sum(case.get("review_status") == "resolved" for case in cases))


def render_case_card(case: Dict[str, Any]) -> None:
    case_id = display_value(case.get("case_id"), "Unknown case")
    st.markdown(
        """
        <div class="case-card"><h3>{title}</h3><div>{entity}</div>
        <div style="margin-top:.55rem;">{risk} {verification} {status}</div>
        <div class="case-meta">Case {case_id} | Overseas: {overseas} | Received: {created}</div></div>
        """.format(
            title=escape(display_value(case.get("title"), "Title not provided")),
            entity=escape(display_value(case.get("entity_name"), "Entity not provided")),
            risk=risk_badge(case.get("risk_level")),
            verification=verification_badge(case.get("verification_status")),
            status=status_badge(case.get("review_status")),
            case_id=escape(case_id),
            overseas=escape(format_boolean(case.get("is_overseas"))),
            created=escape(format_datetime(case.get("created_at"))),
        ),
        unsafe_allow_html=True,
    )
    if st.button("Review", key="review_{}".format(case_id)):
        st.session_state.selected_case_id = case_id
        st.rerun()


def render_overview(cases: List[Dict[str, Any]]) -> None:
    st.header("Overview")
    render_summary(cases)
    st.subheader("Trends and insights")
    render_overview_analytics(cases)
    st.subheader("Recent priority cases")
    priority = [
        case for case in cases
        if case.get("risk_level") == "high_risk"
        or case.get("verification_status") == "blacklisted"
    ][:5]
    if not priority:
        st.info("No priority cases match the current filters.")
    for case in priority:
        render_case_card(case)


def render_queue(cases: List[Dict[str, Any]], dates_invalid: bool) -> None:
    """Render the filtered government queue with an explicit refresh control."""
    heading_column, refresh_column = st.columns([5, 1])

    with heading_column:
        st.header("Review queue")
        st.caption(
            "Review suspicious and high-risk referrals using the current filters."
        )

    with refresh_column:
        st.write("")
        if st.button(
            "Refresh queue",
            key="refresh_review_queue",
            type="secondary",
            width="stretch",
        ):
            st.rerun()

    if dates_invalid:
        st.error("From date must be on or before To date.")
        return

    render_summary(cases)

    st.caption(
        "{} case{} in the current filtered view".format(
            len(cases),
            "" if len(cases) == 1 else "s",
        )
    )

    if not cases:
        st.markdown(
            '<div class="empty-state">'
            '<h3>No cases found</h3>'
            '<p>No cases match the selected filters.</p>'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    risk_order = {
        "high_risk": 0,
        "suspicious": 1,
        "lower_risk": 2,
    }

    newest_first = sorted(
        cases,
        key=lambda case: str(case.get("created_at") or ""),
        reverse=True,
    )
    sorted_cases = sorted(
        newest_first,
        key=lambda case: risk_order.get(case.get("risk_level"), 99),
    )

    page_size = 25
    page_count = max(1, (len(sorted_cases) + page_size - 1) // page_size)

    if "queue_page" not in st.session_state:
        st.session_state.queue_page = 1

    st.session_state.queue_page = min(
        max(1, int(st.session_state.queue_page)),
        page_count,
    )

    if page_count > 1:
        previous_column, page_column, next_column = st.columns([1, 3, 1])
        with previous_column:
            if st.button(
                "Previous",
                disabled=st.session_state.queue_page <= 1,
                width="stretch",
            ):
                st.session_state.queue_page -= 1
                st.rerun()
        with page_column:
            st.markdown(
                "<div style='text-align:center;padding:.55rem;'>"
                "Page {} of {}"
                "</div>".format(st.session_state.queue_page, page_count),
                unsafe_allow_html=True,
            )
        with next_column:
            if st.button(
                "Next",
                disabled=st.session_state.queue_page >= page_count,
                width="stretch",
            ):
                st.session_state.queue_page += 1
                st.rerun()

    start = (st.session_state.queue_page - 1) * page_size
    visible_cases = sorted_cases[start:start + page_size]

    header = st.columns([1.1, 2.1, 1.8, 1.15, 1.5, 1.0, 1.15, 0.8])
    for column, label in zip(
        header,
        [
            "Case ID",
            "Title",
            "Entity",
            "Risk",
            "Verification",
            "Market",
            "Received",
            "",
        ],
    ):
        column.markdown("**{}**".format(label))

    st.divider()

    for index, case in enumerate(visible_cases):
        case_id = display_value(case.get("case_id"), "Unknown case")
        row = st.columns([1.1, 2.1, 1.8, 1.15, 1.5, 1.0, 1.15, 0.8])
        row[0].write(case_id)
        row[1].write(display_value(case.get("title"), "Not provided"))
        row[2].write(display_value(case.get("entity_name"), "Not provided"))
        row[3].markdown(risk_badge(case.get("risk_level")), unsafe_allow_html=True)
        row[4].markdown(
            verification_badge(case.get("verification_status")),
            unsafe_allow_html=True,
        )
        row[5].write("Overseas" if case.get("is_overseas") else "Local")
        row[6].write(format_datetime(case.get("created_at")))

        if row[7].button(
            "Review",
            key="queue_review_{}_{}".format(case_id, start + index),
            width="stretch",
        ):
            st.session_state.selected_case_id = case_id
            st.rerun()

        st.divider()

def show_detail(label: str, value: Any) -> None:
    st.markdown("**{}**".format(escape(label)))
    st.write(display_value(value))


def render_decision_form(client: HakikiHireAPIClient, case: Dict[str, Any]) -> None:
    st.subheader("Reviewer decision")
    if case.get("review_status") == "resolved" or case.get("review_outcome"):
        st.success("This case has been resolved. The recorded decision cannot be edited.")
        show_detail("Recorded outcome", format_outcome(case.get("review_outcome")))
        show_detail("Reviewer notes", case.get("review_notes"))
        return
    reviewer = st.session_state.reviewer_profile or {}
    reviewer_name = display_value(
        reviewer.get("display_name") or reviewer.get("username"),
        "Authenticated reviewer",
    )
    with st.form("decision_{}".format(case.get("case_id"))):
        st.caption("Decision will be recorded as {}".format(reviewer_name))
        outcome = st.selectbox(
            "Outcome",
            [item.value for item in ReviewOutcome],
            format_func=format_outcome,
            index=None,
            placeholder="Select a reviewer outcome",
        )
        notes = st.text_area("Decision notes", height=140)
        confirmation = st.checkbox("I confirm that this decision is final and cannot be edited.")
        submitted = st.form_submit_button("Submit decision", type="primary", width="stretch")
    if not submitted:
        return
    if not outcome or not notes.strip() or not confirmation:
        st.error("Select an outcome, enter notes, and confirm the final decision.")
        return
    try:
        client.submit_decision(case["case_id"], outcome, notes, reviewer_name)
        st.session_state.decision_success_message = "The reviewer decision was recorded."
        st.rerun()
    except (ValueError, HakikiHireAPIError) as error:
        st.error(getattr(error, "message", str(error)))


def render_case_detail(client: HakikiHireAPIClient, case_id: str) -> None:
    if st.button("Back to review queue"):
        st.session_state.selected_case_id = None
        st.session_state.pending_navigation = "Review queue"
        st.rerun()
    try:
        case = client.get_case(case_id)
    except HakikiHireAPIError as error:
        handle_api_error(error)
        return
    message = st.session_state.pop("decision_success_message", None)
    if message:
        st.success(message)
    st.header("Case {}".format(display_value(case.get("case_id"))))
    st.markdown(
        "{} {} {}".format(
            risk_badge(case.get("risk_level")),
            verification_badge(case.get("verification_status")),
            status_badge(case.get("review_status")),
        ),
        unsafe_allow_html=True,
    )
    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            st.subheader("Case information")
            show_detail("Posting title", case.get("title"))
            show_detail("Entity", case.get("entity_name"))
            show_detail("Created", format_datetime(case.get("created_at")))
            show_detail("Overseas posting", format_boolean(case.get("is_overseas")))
    with right:
        with st.container(border=True):
            st.subheader("Posting details")
            show_detail("Location", case.get("location"))
            show_detail("Destination country", case.get("destination_country"))
            show_detail("Salary", case.get("salary_text"))
            show_detail("Contact email", case.get("contact_email"))
            show_detail("Model probability", format_probability(case.get("probability")))
    st.subheader("Posting description")
    st.text_area(
        "Description",
        value=display_value(case.get("description"), "No description was provided."),
        disabled=True,
        height=180,
        label_visibility="collapsed",
    )
    render_decision_form(client, case)
    st.subheader("Audit trail")
    audit = case.get("audit_trail") or []
    if not audit:
        st.info("No review activity recorded yet.")
    for entry in audit:
        with st.container(border=True):
            st.write(entry)


def render_reports(
    cases: List[Dict[str, Any]],
    filters: Dict[str, Any],
) -> None:
    st.header("Hakiki Hire Intelligence Report")
    st.caption(
        "Decision outcomes, verification exposure, case intelligence, "
        "and stakeholder-ready export."
    )

    if filters.get("dates_invalid"):
        st.error("From date must be on or before To date.")
        return

    scope = {
        key.replace("_", " ").title(): value
        for key, value in filters.items()
        if key != "dates_invalid" and value not in {None, "", "All"}
    }
    if scope:
        with st.expander("Report scope and applied filters", expanded=False):
            st.json(scope)

    render_report_summary(cases)

    if not cases:
        st.info("No cases match the current reporting scope.")
        return

    st.subheader("Decision intelligence")
    render_report_analytics(cases)

    st.subheader("Export intelligence report")
    st.caption(
        "The PDF contains outcome metrics, verification exposure, key "
        "findings, watchlists, confirmed scams, and the complete case register."
    )

    report_filters = {
        key: value
        for key, value in filters.items()
        if key != "dates_invalid"
    }

    try:
        pdf = generate_summary_report_pdf(
            cases=cases,
            filters=report_filters,
            reviewer=st.session_state.reviewer_profile or {},
        )
    except Exception as error:
        st.error("The PDF intelligence report could not be generated.")
        with st.expander("Technical error details"):
            st.code(str(error))
        return

    st.download_button(
        "Download Hakiki Hire intelligence report",
        data=pdf,
        file_name=report_filename(),
        mime="application/pdf",
        type="primary",
        width="stretch",
    )

def render_access_management(client: HakikiHireAPIClient) -> None:
    reviewer = st.session_state.reviewer_profile or {}
    if reviewer.get("role") != "admin":
        st.error("Administrator access is required.")
        return
    st.header("Access management")
    st.caption("Create and manage authorised Hakiki Hire accounts.")
    try:
        users = client.get_users()
    except HakikiHireAPIError as error:
        handle_api_error(error)
        return
    st.dataframe(
        [
            {
                "Name": user.get("display_name"),
                "Username": user.get("username"),
                "Role": str(user.get("role", "")).title(),
                "Status": "Active" if user.get("is_active") else "Inactive",
            }
            for user in users
        ],
        hide_index=True,
        width="stretch",
    )
    st.subheader("Create account")
    with st.form("create_account", clear_on_submit=True):
        name = st.text_input("Display name")
        username = st.text_input("Username")
        password = st.text_input("Initial password", type="password")
        role = st.selectbox("Role", ["reviewer", "admin"], format_func=str.title)
        active = st.checkbox("Account active", value=True)
        submitted = st.form_submit_button("Create account", type="primary", width="stretch")
    if submitted:
        try:
            client.create_reviewer(username, password, name, role, active)
            st.success("The account was created.")
            st.rerun()
        except (ValueError, HakikiHireAPIError) as error:
            st.error(getattr(error, "message", str(error)))

    current_id = reviewer.get("id")
    st.subheader("Manage accounts")
    for user in users:
        user_id = int(user["id"])
        own_account = user_id == current_id
        with st.container(border=True):
            st.markdown("**{}** · `{}`".format(
                escape(display_value(user.get("display_name"))),
                escape(display_value(user.get("username"))),
            ))
            role_column, status_column = st.columns(2)
            with role_column:
                selected_role = st.selectbox(
                    "Role",
                    ["reviewer", "admin"],
                    index=1 if user.get("role") == "admin" else 0,
                    key="role_{}".format(user_id),
                    disabled=own_account,
                )
                if st.button("Update role", key="role_button_{}".format(user_id), disabled=own_account):
                    try:
                        client.update_user_role(user_id, selected_role)
                        st.rerun()
                    except HakikiHireAPIError as error:
                        st.error(error.message)
            with status_column:
                active = st.checkbox(
                    "Account active",
                    value=bool(user.get("is_active")),
                    key="active_{}".format(user_id),
                    disabled=own_account,
                )
                if st.button("Update status", key="status_button_{}".format(user_id), disabled=own_account):
                    try:
                        client.update_user_status(user_id, active)
                        st.rerun()
                    except HakikiHireAPIError as error:
                        st.error(error.message)


def main() -> None:
    apply_styles()
    initialise_state()

    # Apply navigation requested during the previous Streamlit run before
    # the navigation radio widget is instantiated.
    if "pending_navigation" in st.session_state:
        st.session_state.navigation_page = st.session_state.pop(
            "pending_navigation"
        )
    if not st.session_state.access_token:
        render_login()
        return

    client = create_client()
    if not st.session_state.reviewer_profile:
        try:
            st.session_state.reviewer_profile = client.get_current_user()
        except HakikiHireAPIError as error:
            handle_api_error(error)
            return

    page, filters = render_sidebar(client)
    cases = load_filtered_cases(client, filters)
    render_header()

    if st.session_state.selected_case_id:
        render_case_detail(client, st.session_state.selected_case_id)
    elif page == "Overview":
        render_overview(cases)
    elif page == "Review queue":
        render_queue(cases, filters.get("dates_invalid", False))
    elif page == "Reports":
        render_reports(cases, filters)
    elif page == "Access management":
        render_access_management(client)


if __name__ == "__main__":
    main()
