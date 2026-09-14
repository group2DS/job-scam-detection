"""SafeHire Government Dashboard with authentication and dynamic analytics."""

from html import escape

import streamlit as st

from src.core.schemas import ReviewOutcome

try:
    from app.government.analytics import render_filtered_queue_analytics
    from app.government.api_client import SafeHireAPIClient, SafeHireAPIError
except ImportError:
    from analytics import render_filtered_queue_analytics
    from api_client import SafeHireAPIClient, SafeHireAPIError


st.set_page_config(
    page_title="SafeHire Government Dashboard",
    page_icon="SH",
    layout="wide",
    initial_sidebar_state="expanded",
)

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


def display_value(value, fallback="Not provided"):
    if value is None:
        return fallback
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned or cleaned.lower() in {"none", "null", "nan"}:
            return fallback
        return cleaned
    return str(value)


def format_risk(value):
    return RISK_LABELS.get(value, display_value(value))


def format_verification(value):
    return VERIFICATION_LABELS.get(value, display_value(value))


def format_review_status(value):
    return REVIEW_LABELS.get(value, display_value(value))


def format_outcome(value):
    if value is None:
        return "No decision recorded"
    return OUTCOME_LABELS.get(
        value,
        str(value).replace("_", " ").strip().capitalize(),
    )


def format_probability(value):
    if value is None:
        return "Not provided"
    try:
        probability = max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return "Not provided"
    return "{:.1f}%".format(probability * 100)


def format_datetime(value):
    if value is None:
        return "Not provided"
    text = str(value).strip()
    if not text:
        return "Not provided"
    if "T" in text:
        date_part, time_part = text.split("T", 1)
        return "{} {}".format(date_part, time_part[:5])
    return text


def format_boolean(value):
    if value is True:
        return "Yes"
    if value is False:
        return "No"
    return "Not provided"


def badge_html(label, color):
    return (
        '<span class="badge" style="color:{0};border-color:{0};">{1}</span>'
    ).format(color, escape(label))


def risk_badge(value):
    colors = {
        "lower_risk": "#15803d",
        "suspicious": "#b45309",
        "high_risk": "#b91c1c",
    }
    return badge_html(format_risk(value), colors.get(value, "#475569"))


def verification_badge(value):
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


def apply_styles():
    st.markdown(
        """
        <style>
        :root {
            --navy: #071f33;
            --blue: #0a3a59;
            --cyan: #74d4ff;
            --page: #f4f7fb;
            --text: #10233b;
            --body: #334155;
            --muted: #64748b;
            --border: #dbe3ec;
        }

        .stApp { background: var(--page); }
        .block-container {
            max-width: 1400px;
            padding-top: .8rem;
            padding-bottom: 3rem;
        }

        /* Main content contrast */
        div[data-testid="stMainBlockContainer"] {
            color: var(--body) !important;
        }
        div[data-testid="stMainBlockContainer"] h1,
        div[data-testid="stMainBlockContainer"] h2,
        div[data-testid="stMainBlockContainer"] h3,
        div[data-testid="stMainBlockContainer"] h4,
        div[data-testid="stMainBlockContainer"] h5,
        div[data-testid="stMainBlockContainer"] h6 {
            color: var(--text) !important;
            -webkit-text-fill-color: var(--text) !important;
        }
        div[data-testid="stMainBlockContainer"] p,
        div[data-testid="stMainBlockContainer"] label,
        div[data-testid="stMainBlockContainer"] li {
            color: var(--body) !important;
            -webkit-text-fill-color: var(--body) !important;
        }

        .safehire-hero {
            position: relative;
            overflow: hidden;
            display: flex;
            gap: 1rem;
            min-height: 205px;
            padding: 1.9rem 2rem;
            margin: -.8rem 0 1.8rem;
            background: linear-gradient(135deg, var(--navy), var(--blue));
            border-radius: 0 0 18px 18px;
            box-shadow: 0 18px 34px rgba(15, 23, 42, .22);
        }
        .safehire-hero::after,
        .login-brand-panel::after {
            content: "";
            position: absolute;
            border-radius: 50%;
            border-style: solid;
            border-color: rgba(116, 212, 255, .13);
        }
        .safehire-hero::after {
            width: 170px;
            height: 170px;
            right: -43px;
            bottom: -101px;
            border-width: 25px;
        }
        .hero-icon,
        .login-mark {
            position: relative;
            z-index: 2;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #fff !important;
            -webkit-text-fill-color: #fff !important;
            border: 1px solid rgba(255, 255, 255, .42);
            background: rgba(255, 255, 255, .08);
            border-radius: 14px;
        }
        .hero-icon {
            width: 44px;
            height: 44px;
            flex: 0 0 44px;
            margin-top: 1rem;
        }
        .hero-content { position: relative; z-index: 2; flex: 1; }
        .hero-eyebrow,
        .login-kicker {
            color: var(--cyan) !important;
            -webkit-text-fill-color: var(--cyan) !important;
            font-size: .72rem;
            font-weight: 800;
            letter-spacing: .14em;
            text-transform: uppercase;
        }
        .hero-title {
            color: #fff !important;
            -webkit-text-fill-color: #fff !important;
            font-size: 2rem;
            font-weight: 800;
            line-height: 1.15;
            margin-top: .45rem;
        }
        .hero-description {
            max-width: 760px;
            color: #fff !important;
            -webkit-text-fill-color: #fff !important;
            font-size: .98rem;
            line-height: 1.65;
            margin-top: .85rem;
        }
        .hero-environment {
            display: inline-block;
            color: #fff !important;
            -webkit-text-fill-color: #fff !important;
            background: rgba(255, 255, 255, .06);
            border: 1px solid rgba(255, 255, 255, .46);
            border-radius: 999px;
            font-size: .7rem;
            font-weight: 800;
            margin-top: 1rem;
            padding: .45rem .75rem;
        }

        .login-heading { text-align: center; margin: 1rem 0 1.7rem; }
        .login-heading-title {
            color: var(--navy) !important;
            -webkit-text-fill-color: var(--navy) !important;
            font-size: 1.8rem;
            font-weight: 800;
        }
        .login-heading-copy { color: var(--muted) !important; }
        .login-brand-panel {
            position: relative;
            overflow: hidden;
            min-height: 470px;
            padding: 3rem;
            background: linear-gradient(145deg, var(--navy), var(--blue));
            border-radius: 22px;
            box-shadow: 0 22px 50px rgba(15, 23, 42, .18);
        }
        .login-brand-panel::after {
            width: 290px;
            height: 290px;
            right: -130px;
            bottom: -145px;
            border-width: 42px;
        }
        .login-mark { width: 56px; height: 56px; font-size: 1.5rem; }
        .login-kicker { position: relative; z-index: 2; margin-top: 2rem; }
        .login-title {
            position: relative;
            z-index: 2;
            color: #fff !important;
            -webkit-text-fill-color: #fff !important;
            font-size: 2.35rem;
            font-weight: 800;
            line-height: 1.14;
            margin-top: .65rem;
        }
        .login-copy {
            position: relative;
            z-index: 2;
            color: #dbeafe !important;
            -webkit-text-fill-color: #dbeafe !important;
            line-height: 1.7;
            margin-top: 1rem;
            max-width: 420px;
        }
        .login-chip {
            position: relative;
            z-index: 2;
            display: inline-block;
            margin-top: 2rem;
            padding: .45rem .8rem;
            color: #bae6fd !important;
            -webkit-text-fill-color: #bae6fd !important;
            border-radius: 999px;
            border: 1px solid rgba(255, 255, 255, .22);
            background: rgba(255, 255, 255, .07);
            font-size: .76rem;
            font-weight: 700;
        }
        .login-form-heading {
            color: var(--text) !important;
            -webkit-text-fill-color: var(--text) !important;
            font-size: 1.45rem;
            font-weight: 800;
            margin-top: .3rem;
        }
        .login-form-copy,
        .login-footer { color: var(--muted) !important; }
        .login-footer { text-align: center; font-size: .78rem; margin-top: 1rem; }

        div[data-testid="stForm"] {
            background: #fff !important;
            border: 1px solid var(--border) !important;
            border-radius: 18px !important;
            box-shadow: 0 20px 44px rgba(15, 23, 42, .11);
            padding: 1.5rem !important;
        }
        div[data-testid="stFormSubmitButton"] button {
            min-height: 46px !important;
            color: #fff !important;
            border: none !important;
            border-radius: 9px !important;
            font-weight: 750 !important;
            background: linear-gradient(135deg, #075985, #0a6a96) !important;
        }
        div[data-testid="stFormSubmitButton"] button p {
            color: #fff !important;
            -webkit-text-fill-color: #fff !important;
        }

        .badge {
            display: inline-block;
            background: #fff;
            border: 1px solid;
            border-radius: 999px;
            font-size: .8rem;
            font-weight: 700;
            margin-right: .3rem;
            padding: .22rem .65rem;
        }
        .case-card,
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background: #fff !important;
            border: 1px solid var(--border) !important;
            border-radius: 14px !important;
            box-shadow: 0 4px 14px rgba(15, 23, 42, .05);
        }
        .case-card { margin-bottom: .65rem; padding: 1.1rem; }
        .case-card h3 { color: #0f172a !important; margin: 0 0 .3rem; }
        .case-entity { color: var(--body) !important; }
        .case-meta { color: var(--muted) !important; font-size: .84rem; margin-top: .6rem; }
        .empty-state {
            background: #fff;
            border: 1px dashed #94a3b8;
            border-radius: 14px;
            padding: 2rem;
            text-align: center;
        }
        div[data-testid="stMetric"] {
            background: #fff;
            border: 1px solid var(--border);
            border-radius: 14px;
            box-shadow: 0 3px 12px rgba(15, 23, 42, .04);
            padding: 1rem;
        }
        div[data-testid="stMetricValue"] { color: #0f172a !important; font-weight: 800; }
        div[data-testid="stTextInput"] input,
        div[data-testid="stTextArea"] textarea,
        div[data-baseweb="select"] > div {
            background: #fff !important;
            color: #0f172a !important;
            border-color: #cbd5e1 !important;
        }
        textarea:disabled {
            background: #fff !important;
            color: var(--body) !important;
            -webkit-text-fill-color: var(--body) !important;
            border: 1px solid #cbd5e1 !important;
            opacity: 1 !important;
        }
        div[data-testid="stCaptionContainer"] p {
            color: var(--muted) !important;
            -webkit-text-fill-color: var(--muted) !important;
        }

        .reviewer-panel {
            background: rgba(255, 255, 255, .08);
            border: 1px solid rgba(255, 255, 255, .18);
            border-radius: 12px;
            margin: .8rem 0 1rem;
            padding: .85rem;
        }
        .reviewer-name {
            color: #fff !important;
            -webkit-text-fill-color: #fff !important;
            font-weight: 750;
        }
        .reviewer-role {
            color: #bae6fd !important;
            -webkit-text-fill-color: #bae6fd !important;
            font-size: .76rem;
            margin-top: .15rem;
            text-transform: capitalize;
        }

        section[data-testid="stSidebar"],
        section[data-testid="stSidebar"] > div,
        section[data-testid="stSidebar"] div[data-testid="stSidebarContent"] {
            background: linear-gradient(180deg, var(--navy), var(--blue)) !important;
        }
        section[data-testid="stSidebar"] { border-right: 1px solid #164e63 !important; }
        section[data-testid="stSidebar"] h1,
        section[data-testid="stSidebar"] h2,
        section[data-testid="stSidebar"] h3,
        section[data-testid="stSidebar"] p,
        section[data-testid="stSidebar"] label,
        section[data-testid="stSidebar"] span {
            color: #fff !important;
            -webkit-text-fill-color: #fff !important;
        }
        section[data-testid="stSidebar"] div[data-baseweb="select"] > div,
        section[data-testid="stSidebar"] div[data-testid="stDateInput"] input {
            background: rgba(255, 255, 255, .10) !important;
            border-color: rgba(255, 255, 255, .28) !important;
            color: #fff !important;
            -webkit-text-fill-color: #fff !important;
        }
        section[data-testid="stSidebar"] hr { border-color: rgba(255, 255, 255, .20) !important; }
        section[data-testid="stSidebar"] div[data-testid="stAlert"] {
            background: rgba(220, 252, 231, .96) !important;
        }
        section[data-testid="stSidebar"] div[data-testid="stAlert"] p,
        section[data-testid="stSidebar"] div[data-testid="stAlert"] span {
            color: #166534 !important;
            -webkit-text-fill-color: #166534 !important;
        }

        @media (max-width: 850px) {
            .login-brand-panel { min-height: auto; padding: 2rem; }
            .login-title { font-size: 1.9rem; }
            .hero-icon { display: none; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def initialise_state():
    defaults = {
        "selected_case_id": None,
        "api_environment": "Local API",
        "access_token": None,
        "reviewer_profile": None,
        "login_error": None,
        "filter_risk": "All",
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


def create_client():
    live = st.session_state.get("api_environment") == "Live API"
    return SafeHireAPIClient(
        base_url=LIVE_API_URL if live else LOCAL_API_URL,
        timeout=45 if live else 30,
        access_token=st.session_state.get("access_token"),
    )


def clear_authentication():
    st.session_state.access_token = None
    st.session_state.reviewer_profile = None
    st.session_state.selected_case_id = None


def handle_api_error(error):
    if error.status_code == 401:
        clear_authentication()
        st.session_state.login_error = (
            "Your session has expired. Please sign in again."
        )
        st.rerun()
    st.error(error.message)
    if error.details:
        with st.expander("Technical error details"):
            st.json(error.details)


def hide_sidebar_for_login():
    st.markdown(
        """
        <style>
        section[data-testid="stSidebar"],
        button[data-testid="stSidebarCollapsedControl"],
        div[data-testid="collapsedControl"] {
            display: none !important;
        }
        .block-container {
            max-width: 1120px !important;
            padding-top: 1.4rem !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_login():
    hide_sidebar_for_login()
    st.markdown(
        """
        <div class="login-heading">
            <div class="login-heading-title">SafeHire Government Portal</div>
            <div class="login-heading-copy">
                Protected access for authorised government reviewers
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    brand_column, form_column = st.columns([1.08, .92], gap="large")
    with brand_column:
        st.markdown(
            """
            <div class="login-brand-panel">
                <div class="login-mark">◇</div>
                <div class="login-kicker">Government Review Portal</div>
                <div class="login-title">SafeHire<br>Reviewer Access</div>
                <div class="login-copy">
                    Review referred job postings, examine risk and verification
                    evidence, and record accountable decisions through the
                    protected portal.
                </div>
                <div class="login-chip">Secure reviewer authentication</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with form_column:
        st.markdown(
            """
            <div class="login-form-heading">Welcome back</div>
            <div class="login-form-copy">
                Sign in using your authorised reviewer account.
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.session_state.get("login_error"):
            st.error(st.session_state.pop("login_error"))

        environment = st.selectbox(
            "API environment",
            ["Local API", "Live API"],
            key="login_environment",
        )
        st.session_state.api_environment = environment

        with st.form("reviewer_login_form", clear_on_submit=False):
            username = st.text_input(
                "Username",
                placeholder="Enter your username",
            )
            password = st.text_input(
                "Password",
                type="password",
                placeholder="Enter your password",
            )
            submitted = st.form_submit_button(
                "Sign in securely",
                type="primary",
                width="stretch",
            )

        st.markdown(
            '<div class="login-footer">'
            "Access is restricted to authorised reviewers."
            "</div>",
            unsafe_allow_html=True,
        )

        if not submitted:
            return
        if not username.strip():
            st.error("Enter your username.")
            return
        if not password:
            st.error("Enter your password.")
            return

        client = create_client()
        try:
            with st.spinner("Verifying reviewer credentials..."):
                result = client.login(username, password)
                reviewer = result.get("reviewer")
                if not isinstance(reviewer, dict):
                    reviewer = client.get_current_user()
            st.session_state.access_token = client.access_token
            st.session_state.reviewer_profile = reviewer
            st.session_state.selected_case_id = None
            st.rerun()
        except ValueError as error:
            st.error(str(error))
        except SafeHireAPIError as error:
            st.error(error.message)


def render_header():
    environment = (
        "LIVE API"
        if st.session_state.get("api_environment") == "Live API"
        else "LOCAL API"
    )
    st.markdown(
        """
        <div class="safehire-hero">
            <div class="hero-icon">◇</div>
            <div class="hero-content">
                <div class="hero-eyebrow">GOVERNMENT REVIEW PORTAL</div>
                <div class="hero-title">SafeHire Government<br>Dashboard</div>
                <div class="hero-description">
                    Review referred job postings, examine risk and verification
                    evidence, and record accountable reviewer decisions.
                </div>
                <div class="hero-environment">{environment}</div>
            </div>
        </div>
        """.format(environment=environment),
        unsafe_allow_html=True,
    )


def reset_filters():
    st.session_state.filter_risk = "All"
    st.session_state.filter_status = "All"
    st.session_state.filter_market = "All"
    st.session_state.filter_country = "All"
    st.session_state.filter_date_from = None
    st.session_state.filter_date_to = None
    st.session_state.filter_limit = 200


def render_sidebar(client):
    st.sidebar.title("SafeHire")
    reviewer = st.session_state.get("reviewer_profile") or {}
    name = display_value(
        reviewer.get("display_name") or reviewer.get("username"),
        "Authenticated reviewer",
    )
    role = display_value(reviewer.get("role"), "reviewer")
    st.sidebar.markdown(
        """
        <div class="reviewer-panel">
            <div class="reviewer-name">{name}</div>
            <div class="reviewer-role">{role}</div>
        </div>
        """.format(name=escape(name), role=escape(role)),
        unsafe_allow_html=True,
    )

    if st.sidebar.button("Sign out", width="stretch"):
        client.logout()
        clear_authentication()
        st.rerun()

    try:
        country_options = client.get_destination_countries()
    except SafeHireAPIError as error:
        handle_api_error(error)
        country_options = []

    valid_country_options = ["All", *country_options]
    if st.session_state.get("filter_country", "All") not in valid_country_options:
        st.session_state.filter_country = "All"

    st.sidebar.divider()
    st.sidebar.subheader("Queue filters")
    risk_label = st.sidebar.selectbox(
        "Risk level",
        ["All", "Lower risk", "Suspicious", "High risk"],
        key="filter_risk",
    )
    review_label = st.sidebar.selectbox(
        "Review status",
        ["All", "Open", "Resolved"],
        key="filter_status",
    )
    market_label = st.sidebar.selectbox(
        "Market",
        ["All", "Local", "Overseas"],
        key="filter_market",
    )
    country_label = st.sidebar.selectbox(
        "Destination country",
        valid_country_options,
        key="filter_country",
    )
    date_from = st.sidebar.date_input(
        "From date",
        value=st.session_state.get("filter_date_from"),
        key="filter_date_from",
    )
    date_to = st.sidebar.date_input(
        "To date",
        value=st.session_state.get("filter_date_to"),
        key="filter_date_to",
    )
    limit = st.sidebar.slider(
        "Maximum cases",
        min_value=1,
        max_value=200,
        key="filter_limit",
    )

    dates_invalid = bool(date_from and date_to and date_from > date_to)
    if dates_invalid:
        st.sidebar.error("From date must be on or before To date.")

    if st.sidebar.button("Refresh dashboard", width="stretch"):
        st.rerun()
    st.sidebar.button(
        "Reset filters",
        on_click=reset_filters,
        width="stretch",
    )

    st.sidebar.divider()
    st.sidebar.subheader("Service status")
    try:
        health = client.health()
        st.sidebar.success("API available")
        st.sidebar.write(
            "Version: {}".format(display_value(health.get("version")))
        )
        st.sidebar.write(
            "Model: {}".format(display_value(health.get("model")))
        )
    except SafeHireAPIError as error:
        handle_api_error(error)

    return {
        "risk_level": {
            "All": None,
            "Lower risk": "lower_risk",
            "Suspicious": "suspicious",
            "High risk": "high_risk",
        }[risk_label],
        "review_status": {
            "All": None,
            "Open": "open",
            "Resolved": "resolved",
        }[review_label],
        "is_overseas": {
            "All": None,
            "Local": False,
            "Overseas": True,
        }[market_label],
        "destination_country": (
            None if country_label == "All" else country_label
        ),
        "date_from": date_from.isoformat() if date_from else None,
        "date_to": date_to.isoformat() if date_to else None,
        "limit": limit,
        "dates_invalid": dates_invalid,
    }


def find_stat(stats, keys):
    for key in keys:
        if key in stats:
            return stats[key]
    return "Not available"


def render_statistics(client):
    st.subheader("Queue summary")
    try:
        stats = client.get_stats()
    except SafeHireAPIError as error:
        handle_api_error(error)
        return

    columns = st.columns(4)
    columns[0].metric(
        "Total cases",
        find_stat(stats, ["total", "total_cases", "cases"]),
    )
    columns[1].metric(
        "Open cases",
        find_stat(stats, ["open", "open_cases"]),
    )
    columns[2].metric(
        "High risk",
        find_stat(stats, ["high_risk", "high_risk_cases"]),
    )
    columns[3].metric(
        "Resolved",
        find_stat(stats, ["resolved", "resolved_cases"]),
    )


def render_case_card(case):
    case_id = display_value(case.get("case_id"), "Unknown case")
    title = display_value(case.get("title"), "Title not provided")
    entity = display_value(case.get("entity_name"), "Entity not provided")
    left, action = st.columns([5, 1])

    with left:
        st.markdown(
            """
            <div class="case-card">
                <h3>{title}</h3>
                <div class="case-entity">{entity}</div>
                <div style="margin-top:.55rem;">{risk} {verification}</div>
                <div class="case-meta">
                    Case {case_id} | Review status: {status} |
                    Overseas: {overseas} | Received: {created}
                </div>
            </div>
            """.format(
                title=escape(title),
                entity=escape(entity),
                risk=risk_badge(case.get("risk_level")),
                verification=verification_badge(
                    case.get("verification_status")
                ),
                case_id=escape(case_id),
                status=escape(
                    format_review_status(case.get("review_status"))
                ),
                overseas=escape(
                    format_boolean(case.get("is_overseas"))
                ),
                created=escape(format_datetime(case.get("created_at"))),
            ),
            unsafe_allow_html=True,
        )

    with action:
        if st.button(
            "Review",
            key="review_{}".format(case_id),
            width="stretch",
        ):
            st.session_state.selected_case_id = case_id
            st.rerun()


def render_queue(client, filters):
    if filters.pop("dates_invalid", False):
        st.error("From date must be on or before To date.")
        return

    try:
        cases = client.get_cases(**filters)
    except ValueError as error:
        st.error(str(error))
        return
    except SafeHireAPIError as error:
        handle_api_error(error)
        return

    render_filtered_queue_analytics(cases)
    st.divider()
    st.subheader("Filtered cases")
    st.caption(
        "{} case{} in the current view".format(
            len(cases),
            "" if len(cases) == 1 else "s",
        )
    )

    if not cases:
        st.markdown(
            '<div class="empty-state"><h3>No cases found</h3>'
            '<p>No referred cases match the selected filters.</p></div>',
            unsafe_allow_html=True,
        )
        return

    for case in cases:
        render_case_card(case)


def show_detail(label, value):
    st.markdown("**{}**".format(label))
    st.write(display_value(value))


def render_decision_form(client, case):
    st.markdown("### Reviewer decision")
    case_id = case.get("case_id")

    if case.get("review_status") == "resolved" or case.get("review_outcome"):
        st.success(
            "This case has been resolved. The recorded decision cannot be edited."
        )
        show_detail(
            "Recorded outcome",
            format_outcome(case.get("review_outcome")),
        )
        show_detail("Reviewer notes", case.get("review_notes"))
        show_detail(
            "Reviewed at",
            format_datetime(case.get("reviewed_at")),
        )
        return

    reviewer = st.session_state.get("reviewer_profile") or {}
    reviewer_name = display_value(
        reviewer.get("display_name") or reviewer.get("username"),
        "Authenticated reviewer",
    )
    outcomes = [item.value for item in ReviewOutcome]

    with st.form(
        "decision_form_{}".format(display_value(case_id, "unknown"))
    ):
        st.caption("Decision will be recorded as {}".format(reviewer_name))
        st.caption(
            "All submitted outcomes are final, including 'Needs more evidence'."
        )
        outcome = st.selectbox(
            "Outcome",
            outcomes,
            format_func=format_outcome,
            index=None,
            placeholder="Select a reviewer outcome",
        )
        notes = st.text_area(
            "Decision notes",
            placeholder=(
                "Record the evidence considered and explain the decision."
            ),
            height=140,
        )
        confirmation = st.checkbox(
            "I confirm that this decision is final and cannot be edited."
        )
        submitted = st.form_submit_button(
            "Submit decision",
            type="primary",
            width="stretch",
        )

    if not submitted:
        return
    if not outcome:
        st.error("Select a reviewer outcome.")
        return
    if not confirmation:
        st.error("Confirm that the decision is final before submitting.")
        return

    try:
        with st.spinner("Recording reviewer decision..."):
            client.submit_decision(
                case_id=case_id,
                outcome=outcome,
                notes=notes,
                reviewer=reviewer_name,
            )
        st.session_state.decision_success_message = (
            "The reviewer decision was recorded."
        )
        st.rerun()
    except SafeHireAPIError as error:
        handle_api_error(error)
    except ValueError as error:
        st.error(str(error))


def render_case_detail(client, case_id):
    if st.button("Back to queue"):
        st.session_state.selected_case_id = None
        st.rerun()

    if "decision_success_message" in st.session_state:
        st.success(st.session_state.pop("decision_success_message"))

    try:
        case = client.get_case(case_id)
    except SafeHireAPIError as error:
        handle_api_error(error)
        return

    st.subheader("Case {}".format(display_value(case.get("case_id"))))
    risk_column, verification_column = st.columns(2)
    with risk_column:
        st.markdown("**Risk assessment**")
        st.markdown(
            risk_badge(case.get("risk_level")),
            unsafe_allow_html=True,
        )
    with verification_column:
        st.markdown("**Verification status**")
        st.markdown(
            verification_badge(case.get("verification_status")),
            unsafe_allow_html=True,
        )

    st.divider()
    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            st.markdown("### Case information")
            show_detail("Posting title", case.get("title"))
            show_detail("Entity", case.get("entity_name"))
            show_detail(
                "Review status",
                format_review_status(case.get("review_status")),
            )
            show_detail(
                "Created",
                format_datetime(case.get("created_at")),
            )
            show_detail(
                "Overseas posting",
                format_boolean(case.get("is_overseas")),
            )

    with right:
        with st.container(border=True):
            st.markdown("### Posting details")
            show_detail("Location", case.get("location"))
            show_detail(
                "Destination country",
                case.get("destination_country"),
            )
            show_detail("Salary", case.get("salary_text"))
            show_detail("Contact email", case.get("contact_email"))
            show_detail(
                "Model probability",
                format_probability(case.get("probability")),
            )

    st.markdown("### Posting description")
    st.text_area(
        "Description",
        value=display_value(
            case.get("description"),
            "No posting description was provided.",
        ),
        height=180,
        disabled=True,
        label_visibility="collapsed",
    )

    st.markdown("### Assessment reasons")
    reasons = case.get("reasons") or []
    if not reasons:
        st.info("No assessment reasons were provided.")
    else:
        for reason in reasons:
            if isinstance(reason, dict):
                with st.container(border=True):
                    st.write(display_value(reason.get("text")))
                    st.caption(
                        "Code: {} | Source: {}".format(
                            display_value(reason.get("code")),
                            display_value(reason.get("source")),
                        )
                    )
            else:
                st.write(display_value(reason))

    st.divider()
    render_decision_form(client, case)
    st.divider()

    st.markdown("### Audit trail")
    audit_trail = case.get("audit_trail") or []
    if not audit_trail:
        st.info("No review activity recorded yet.")
    else:
        for entry in audit_trail:
            if isinstance(entry, dict):
                st.json(entry)
            else:
                st.write(display_value(entry))


def main():
    apply_styles()
    initialise_state()

    if not st.session_state.get("access_token"):
        render_login()
        return

    client = create_client()
    if not st.session_state.get("reviewer_profile"):
        try:
            st.session_state.reviewer_profile = client.get_current_user()
        except SafeHireAPIError as error:
            handle_api_error(error)
            return

    render_header()
    filters = render_sidebar(client)

    if st.session_state.selected_case_id:
        render_case_detail(client, st.session_state.selected_case_id)
    else:
        render_statistics(client)
        st.write("")
        render_queue(client, filters)


if __name__ == "__main__":
    main()
