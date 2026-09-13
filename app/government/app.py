from html import escape

import streamlit as st

from src.core.schemas import ReviewOutcome

try:
    from app.government.api_client import SafeHireAPIClient, SafeHireAPIError
except ModuleNotFoundError:
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

REVIEW_LABELS = {
    "open": "Open",
    "resolved": "Resolved",
}

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
            --safehire-navy: #071f33;
            --safehire-blue: #0a3a59;
            --safehire-light-blue: #74d4ff;
            --safehire-page: #f4f7fb;
            --safehire-text: #10233b;
            --safehire-muted: #64748b;
            --safehire-border: #dbe3ec;
        }

        .stApp {
            background-color: var(--safehire-page);
        }

        .block-container {
            max-width: 1400px;
            padding-top: 0.8rem;
            padding-bottom: 3rem;
        }

        .safehire-hero {
            position: relative;
            display: flex;
            align-items: flex-start;
            gap: 1rem;
            min-height: 220px;
            overflow: hidden;
            background: linear-gradient(
                135deg,
                var(--safehire-navy) 0%,
                var(--safehire-blue) 100%
            );
            border-radius: 0 0 18px 18px;
            box-shadow: 0 18px 34px rgba(15, 23, 42, 0.22);
            padding: 1.9rem 2rem 1.8rem 1.9rem;
            margin: -0.8rem 0 1.8rem 0;
        }

        .safehire-hero::after {
            content: "";
            position: absolute;
            z-index: 0;
            width: 170px;
            height: 170px;
            right: -43px;
            bottom: -101px;
            border: 25px solid rgba(63, 145, 188, 0.18);
            border-radius: 50%;
        }

        .hero-icon {
            position: relative;
            z-index: 2;
            display: flex;
            align-items: center;
            justify-content: center;
            flex: 0 0 44px;
            width: 44px;
            height: 44px;
            margin-top: 1rem;
            color: #ffffff !important;
            border: 1px solid rgba(255, 255, 255, 0.42);
            border-radius: 12px;
            background-color: rgba(255, 255, 255, 0.08);
            font-size: 1.25rem;
        }

        .hero-icon span {
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
        }

        .hero-content {
            position: relative;
            z-index: 2;
            flex: 1;
        }

        .hero-eyebrow {
            color: var(--safehire-light-blue) !important;
            -webkit-text-fill-color: var(--safehire-light-blue) !important;
            font-size: 0.72rem;
            font-weight: 800;
            letter-spacing: 0.14em;
            line-height: 1.3;
            margin-bottom: 0.45rem;
            text-transform: uppercase;
        }

        .hero-title {
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
            font-size: 2rem;
            font-weight: 800;
            letter-spacing: -0.025em;
            line-height: 1.15;
            margin: 0;
        }

        .hero-description {
            max-width: 760px;
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
            font-size: 0.98rem;
            font-weight: 500;
            line-height: 1.65;
            margin-top: 0.85rem;
        }

        .hero-environment {
            display: inline-block;
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
            background-color: rgba(255, 255, 255, 0.06);
            border: 1px solid rgba(255, 255, 255, 0.46);
            border-radius: 999px;
            font-size: 0.7rem;
            font-weight: 800;
            line-height: 1;
            margin-top: 1rem;
            padding: 0.45rem 0.75rem;
        }

        div[data-testid="stMainBlockContainer"] h1,
        div[data-testid="stMainBlockContainer"] h2,
        div[data-testid="stMainBlockContainer"] h3,
        div[data-testid="stMainBlockContainer"] h4 {
            color: var(--safehire-text) !important;
        }

        div[data-testid="stMainBlockContainer"] p,
        div[data-testid="stMainBlockContainer"] label {
            color: #334155 !important;
        }

        div[data-testid="stCaptionContainer"] p {
            color: var(--safehire-muted) !important;
        }

        div[data-testid="stMainBlockContainer"] .safehire-hero .hero-title,
        div[data-testid="stMainBlockContainer"] .safehire-hero .hero-description,
        div[data-testid="stMainBlockContainer"] .safehire-hero .hero-environment {
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
        }

        div[data-testid="stMainBlockContainer"] .safehire-hero .hero-eyebrow {
            color: var(--safehire-light-blue) !important;
            -webkit-text-fill-color: var(--safehire-light-blue) !important;
        }

        .badge {
            display: inline-block;
            background-color: #ffffff;
            border: 1px solid;
            border-radius: 999px;
            font-size: 0.8rem;
            font-weight: 700;
            margin-right: 0.3rem;
            padding: 0.22rem 0.65rem;
        }

        .case-card {
            background-color: #ffffff;
            border: 1px solid var(--safehire-border);
            border-radius: 14px;
            box-shadow: 0 3px 12px rgba(15, 23, 42, 0.04);
            margin-bottom: 0.65rem;
            padding: 1.1rem;
        }

        .case-card h3 {
            color: #0f172a !important;
            -webkit-text-fill-color: #0f172a !important;
            font-size: 1.05rem;
            margin: 0 0 0.3rem 0;
        }

        .case-card .case-entity {
            color: #334155 !important;
            -webkit-text-fill-color: #334155 !important;
            margin-bottom: 0.45rem;
        }

        .case-meta {
            color: var(--safehire-muted) !important;
            -webkit-text-fill-color: var(--safehire-muted) !important;
            font-size: 0.84rem;
            line-height: 1.5;
            margin-top: 0.6rem;
        }

        .empty-state {
            background-color: #ffffff;
            border: 1px dashed #94a3b8;
            border-radius: 14px;
            color: #475569 !important;
            padding: 2rem;
            text-align: center;
        }

        .empty-state h3 {
            color: #0f172a !important;
        }

        div[data-testid="stMetric"] {
            background-color: #ffffff;
            border: 1px solid var(--safehire-border);
            border-radius: 14px;
            box-shadow: 0 3px 12px rgba(15, 23, 42, 0.04);
            padding: 1rem;
        }

        div[data-testid="stMetric"] label {
            color: #475569 !important;
        }

        div[data-testid="stMetricValue"] {
            color: #0f172a !important;
            font-weight: 800;
        }

        div[data-testid="stTextInput"] label,
        div[data-testid="stTextArea"] label,
        div[data-testid="stSelectbox"] label,
        div[data-testid="stCheckbox"] label {
            color: #334155 !important;
            font-weight: 600;
        }

        div[data-testid="stTextInput"] input,
        div[data-testid="stTextArea"] textarea {
            background-color: #ffffff !important;
            border: 1px solid #cbd5e1 !important;
            color: #0f172a !important;
        }

        div[data-baseweb="select"] > div {
            background-color: #ffffff !important;
            border-color: #cbd5e1 !important;
            color: #0f172a !important;
        }

        div[data-baseweb="select"] span {
            color: #0f172a !important;
        }

        input::placeholder,
        textarea::placeholder {
            color: #94a3b8 !important;
            opacity: 1 !important;
        }

        textarea:disabled {
            background-color: #f8fafc !important;
            color: #334155 !important;
            opacity: 1 !important;
        }

        section[data-testid="stSidebar"] {
            background: linear-gradient(
                180deg,
                var(--safehire-navy) 0%,
                var(--safehire-blue) 100%
            ) !important;
            border-right: 1px solid #164e63 !important;
        }

        section[data-testid="stSidebar"] h1,
        section[data-testid="stSidebar"] h2,
        section[data-testid="stSidebar"] h3,
        section[data-testid="stSidebar"] p,
        section[data-testid="stSidebar"] label {
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
        }

        section[data-testid="stSidebar"] div[data-testid="stCaptionContainer"] p {
            color: #dbeafe !important;
            -webkit-text-fill-color: #dbeafe !important;
        }

        section[data-testid="stSidebar"] hr {
            border-color: rgba(255, 255, 255, 0.20) !important;
        }

        section[data-testid="stSidebar"] div[data-baseweb="select"] > div {
            background-color: rgba(255, 255, 255, 0.10) !important;
            border: 1px solid rgba(255, 255, 255, 0.28) !important;
        }

        section[data-testid="stSidebar"] div[data-baseweb="select"] span,
        section[data-testid="stSidebar"] div[role="radiogroup"] label p,
        section[data-testid="stSidebar"] div[data-testid="stSlider"] p,
        section[data-testid="stSidebar"] div[data-testid="stSlider"] span {
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
        }

        section[data-testid="stSidebar"] div[data-testid="stAlert"] {
            background-color: rgba(220, 252, 231, 0.96) !important;
        }

        section[data-testid="stSidebar"] div[data-testid="stAlert"] p {
            color: #166534 !important;
            -webkit-text-fill-color: #166534 !important;
        }

        button[data-testid="stSidebarCollapseButton"] {
            color: #ffffff !important;
        }

        @media (max-width: 700px) {
            .safehire-hero {
                padding: 1.5rem;
                min-height: auto;
            }
            .hero-icon {
                display: none;
            }
            .hero-title {
                font-size: 1.65rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def initialise_state():
    if "selected_case_id" not in st.session_state:
        st.session_state.selected_case_id = None
    if "api_environment" not in st.session_state:
        st.session_state.api_environment = "Local API"


def create_client():
    if st.session_state.get("api_environment") == "Live API":
        return SafeHireAPIClient(base_url=LIVE_API_URL, timeout=45)
    return SafeHireAPIClient(base_url=LOCAL_API_URL, timeout=30)


def render_header():
    environment_label = (
        "LIVE API"
        if st.session_state.get("api_environment") == "Live API"
        else "LOCAL API"
    )

    st.markdown(
        """
        <div class="safehire-hero">
            <div class="hero-icon" aria-hidden="true"><span>◇</span></div>
            <div class="hero-content">
                <div class="hero-eyebrow">GOVERNMENT REVIEW PORTAL</div>
                <div class="hero-title">SafeHire Government<br>Dashboard</div>
                <div class="hero-description">
                    Review referred job postings, examine risk and verification
                    evidence, and record accountable reviewer decisions.
                </div>
                <div class="hero-environment">{environment_label}</div>
            </div>
        </div>
        """.format(environment_label=environment_label),
        unsafe_allow_html=True,
    )


def render_sidebar(client):
    st.sidebar.title("SafeHire")
    st.sidebar.radio(
        "API environment",
        ["Local API", "Live API"],
        key="api_environment",
    )
    st.sidebar.caption(
        "Connected to live API"
        if st.session_state.api_environment == "Live API"
        else "Connected to local API"
    )

    st.sidebar.divider()
    st.sidebar.subheader("Queue filters")

    risk_label = st.sidebar.selectbox(
        "Risk level",
        ["All", "Lower risk", "Suspicious", "High risk"],
    )
    review_label = st.sidebar.selectbox(
        "Review status",
        ["All", "Open", "Resolved"],
    )
    market_label = st.sidebar.selectbox(
        "Market",
        ["All", "Local", "Overseas"],
    )
    limit = st.sidebar.slider("Maximum cases", 1, 200, 50)

    risk_options = {
        "All": None,
        "Lower risk": "lower_risk",
        "Suspicious": "suspicious",
        "High risk": "high_risk",
    }
    review_options = {
        "All": None,
        "Open": "open",
        "Resolved": "resolved",
    }
    market_options = {
        "All": None,
        "Local": False,
        "Overseas": True,
    }

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
        st.sidebar.error(error.message)

    return {
        "risk_level": risk_options[risk_label],
        "review_status": review_options[review_label],
        "is_overseas": market_options[market_label],
        "limit": limit,
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
        st.warning("Statistics could not be loaded: {}".format(error.message))
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

    with st.expander("View statistics returned by the API"):
        st.json(stats)


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
                <div style="margin-top:0.55rem;">{risk} {verification}</div>
                <div class="case-meta">
                    Case {case_id} | Review status: {review_status} |
                    Overseas: {overseas} | Received: {created_at}
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
                review_status=escape(
                    format_review_status(case.get("review_status"))
                ),
                overseas=escape(format_boolean(case.get("is_overseas"))),
                created_at=escape(format_datetime(case.get("created_at"))),
            ),
            unsafe_allow_html=True,
        )

    with action:
        if st.button(
            "Review",
            key="review_{}".format(case_id),
            use_container_width=True,
        ):
            st.session_state.selected_case_id = case_id
            st.rerun()


def render_queue(client, filters):
    st.subheader("Case queue")

    try:
        cases = client.get_cases(**filters)
    except SafeHireAPIError as error:
        st.error(error.message)
        return

    st.caption(
        "{} case{} in the current view".format(
            len(cases),
            "" if len(cases) == 1 else "s",
        )
    )

    if not cases:
        st.markdown(
            """
            <div class="empty-state">
                <h3>No cases found</h3>
                <p>No referred cases match the selected filters.</p>
            </div>
            """,
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
    review_status = case.get("review_status")
    review_outcome = case.get("review_outcome")

    if review_status == "resolved" or review_outcome:
        st.success(
            "This case has been resolved. The recorded decision cannot be edited."
        )
        show_detail("Recorded outcome", format_outcome(review_outcome))
        show_detail("Reviewer notes", case.get("review_notes"))
        show_detail("Reviewed at", format_datetime(case.get("reviewed_at")))
        return

    outcome_values = [outcome.value for outcome in ReviewOutcome]

    with st.form(
        "decision_form_{}".format(display_value(case_id, "unknown"))
    ):
        outcome = st.selectbox(
            "Outcome",
            outcome_values,
            format_func=format_outcome,
            index=None,
            placeholder="Select a reviewer outcome",
        )
        reviewer = st.text_input(
            "Reviewer name",
            placeholder="Enter the reviewer name",
        )
        notes = st.text_area(
            "Decision notes",
            placeholder="Record the evidence considered and explain the decision.",
            height=140,
        )
        confirmation = st.checkbox(
            "I confirm that this decision is final and cannot be edited."
        )
        submitted = st.form_submit_button(
            "Submit decision",
            type="primary",
            use_container_width=True,
        )

    if not submitted:
        return
    if not outcome:
        st.error("Select a reviewer outcome.")
        return
    if not reviewer.strip():
        st.error("Enter the reviewer name before submitting.")
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
                reviewer=reviewer,
            )
        st.session_state.decision_success_message = (
            "The reviewer decision was recorded."
        )
        st.rerun()
    except SafeHireAPIError as error:
        st.error(error.message)
        if error.details:
            with st.expander("Technical error details"):
                st.json(error.details)
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
        st.error(error.message)
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
    left_column, right_column = st.columns(2)

    with left_column:
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

    with right_column:
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
    render_header()

    client = create_client()
    filters = render_sidebar(client)

    if st.session_state.selected_case_id:
        render_case_detail(
            client,
            st.session_state.selected_case_id,
        )
    else:
        render_statistics(client)
        st.write("")
        render_queue(client, filters)


if __name__ == "__main__":
    main()
