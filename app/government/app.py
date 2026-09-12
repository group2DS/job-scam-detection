import streamlit as st
from src.core.schemas import ReviewOutcome

try:
    from app.government.api_client import (
        SafeHireAPIClient,
        SafeHireAPIError,
    )
except ModuleNotFoundError:
    from api_client import SafeHireAPIClient, SafeHireAPIError


st.set_page_config(
    page_title="SafeHire Government Dashboard",
    page_icon="SH",
    layout="wide",
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
        value = value.strip()

        if not value:
            return fallback

    return str(value)


def format_risk(value):
    return RISK_LABELS.get(
        value,
        display_value(value),
    )


def format_verification(value):
    return VERIFICATION_LABELS.get(
        value,
        display_value(value),
    )


def format_review_status(value):
    return REVIEW_LABELS.get(
        value,
        display_value(value),
    )

def format_outcome(value):
    if value is None:
        return "No decision recorded"

    if value in OUTCOME_LABELS:
        return OUTCOME_LABELS[value]

    return str(value).replace("_", " ").strip().title()
    


def format_probability(value):
    if value is None:
        return "Not provided"

    try:
        probability = float(value)
    except (TypeError, ValueError):
        return "Not provided"

    return "{:.1f}%".format(probability * 100)


def format_datetime(value):
    if value is None:
        return "Not provided"

    text = str(value)

    if "T" in text:
        date_part, time_part = text.split("T", 1)
        time_part = time_part[:5]
        return "{} {}".format(date_part, time_part)

    return text


def format_boolean(value):
    if value is True:
        return "Yes"

    if value is False:
        return "No"

    return "Not provided"


def risk_badge(value):
    colors = {
        "lower_risk": "#15803d",
        "suspicious": "#b45309",
        "high_risk": "#b91c1c",
    }

    color = colors.get(value, "#475569")
    label = format_risk(value)

    return (
        '<span class="badge" '
        'style="color:{0}; border-color:{0};">'
        "{1}</span>"
    ).format(color, label)


def verification_badge(value):
    colors = {
        "verified": "#15803d",
        "unverified": "#b45309",
        "blacklisted": "#b91c1c",
        "possible_impersonation": "#b45309",
        "not_applicable": "#475569",
    }

    color = colors.get(value, "#475569")
    label = format_verification(value)

    return (
        '<span class="badge" '
        'style="color:{0}; border-color:{0};">'
        "{1}</span>"
    ).format(color, label)


def apply_styles():
    st.markdown(
        """
        <style>
        .stApp {
            background-color: #f5f7fb;
        }

        .block-container {
            max-width: 1400px;
            padding-top: 1.5rem;
            padding-bottom: 3rem;
        }

        .dashboard-header {
            background-color: #123b5d;
            border-radius: 14px;
            color: white;
            padding: 1.4rem 1.6rem;
            margin-bottom: 1rem;
        }

        .dashboard-header h1 {
            margin: 0;
            font-size: 1.8rem;
        }

        .dashboard-header p {
            color: #dbeafe;
            margin: 0.4rem 0 0 0;
        }

        .disclaimer {
            background-color: #fff7ed;
            border: 1px solid #fed7aa;
            border-radius: 10px;
            color: #9a3412;
            padding: 0.75rem 1rem;
            margin-bottom: 1.2rem;
        }

        .badge {
            display: inline-block;
            background-color: white;
            border: 1px solid;
            border-radius: 999px;
            font-size: 0.8rem;
            font-weight: 700;
            padding: 0.22rem 0.65rem;
            margin-right: 0.3rem;
        }

        .case-card {
            background-color: white;
            border: 1px solid #dbe3ec;
            border-radius: 12px;
            padding: 1rem;
            margin-bottom: 0.6rem;
        }

        .case-card h3 {
            color: #0f172a;
            font-size: 1.05rem;
            margin: 0 0 0.3rem 0;
        }

        .case-meta {
            color: #64748b;
            font-size: 0.84rem;
            margin-top: 0.55rem;
        }

        .empty-state {
            background-color: white;
            border: 1px dashed #94a3b8;
            border-radius: 12px;
            color: #475569;
            padding: 2rem;
            text-align: center;
        }

        div[data-testid="stMetric"] {
            background-color: white;
            border: 1px solid #dbe3ec;
            border-radius: 12px;
            padding: 1rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def initialise_state():
    if "selected_case_id" not in st.session_state:
        st.session_state.selected_case_id = None


def create_client():
    environment = st.session_state.get(
        "api_environment",
        "Local API",
    )

    if environment == "Live API":
        return SafeHireAPIClient(
            base_url=LIVE_API_URL,
            timeout=45,
        )

    return SafeHireAPIClient(
        base_url=LOCAL_API_URL,
        timeout=30,
    )


def render_header():
    st.markdown(
        """
        <div class="dashboard-header">
            <h1>SafeHire Government Dashboard</h1>
            <p>
                Review referred job postings and record
                evidence-based decisions.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="disclaimer">
            Registry information is simulated. This student capstone
            is not an official government verification service.
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar(client):
    st.sidebar.title("SafeHire")

    st.sidebar.radio(
        "API environment",
        options=["Local API", "Live API"],
        key="api_environment",
    )

    if st.session_state.api_environment == "Live API":
        st.sidebar.caption("Connected to deployed API")
    else:
        st.sidebar.caption("Connected to local API")

    st.sidebar.divider()
    st.sidebar.subheader("Queue filters")

    risk_label = st.sidebar.selectbox(
        "Risk level",
        [
            "All",
            "Lower risk",
            "Suspicious",
            "High risk",
        ],
    )

    review_label = st.sidebar.selectbox(
        "Review status",
        [
            "All",
            "Open",
            "Resolved",
        ],
    )

    market_label = st.sidebar.selectbox(
        "Market",
        [
            "All",
            "Local",
            "Overseas",
        ],
    )

    limit = st.sidebar.slider(
        "Maximum cases",
        min_value=1,
        max_value=200,
        value=50,
    )

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
            "Version: {}".format(
                display_value(health.get("version"))
            )
        )
        st.sidebar.write(
            "Model: {}".format(
                display_value(health.get("model"))
            )
        )
    except SafeHireAPIError as error:
        st.sidebar.error(error.message)

    return {
        "risk_level": risk_options[risk_label],
        "review_status": review_options[review_label],
        "is_overseas": market_options[market_label],
        "limit": limit,
    }


def find_stat(stats, possible_names):
    for name in possible_names:
        if name in stats:
            return stats[name]

    return "Not available"


def render_statistics(client):
    st.subheader("Queue summary")

    try:
        stats = client.get_stats()
    except SafeHireAPIError as error:
        st.warning(
            "Statistics could not be loaded: {}".format(
                error.message
            )
        )
        return

    columns = st.columns(4)

    columns[0].metric(
        "Total cases",
        find_stat(
            stats,
            ["total", "total_cases", "cases"],
        ),
    )

    columns[1].metric(
        "Open cases",
        find_stat(
            stats,
            ["open", "open_cases"],
        ),
    )

    columns[2].metric(
        "High risk",
        find_stat(
            stats,
            ["high_risk", "high_risk_cases"],
        ),
    )

    columns[3].metric(
        "Resolved",
        find_stat(
            stats,
            ["resolved", "resolved_cases"],
        ),
    )

    with st.expander("View statistics returned by the API"):
        st.json(stats)


def render_case_card(case):
    case_id = display_value(
        case.get("case_id"),
        "Unknown case",
    )

    title = display_value(
        case.get("title"),
        "Title not provided",
    )

    entity = display_value(
        case.get("entity_name"),
        "Entity not provided",
    )

    left_column, action_column = st.columns([5, 1])

    with left_column:
        st.markdown(
            """
            <div class="case-card">
                <h3>{title}</h3>
                <div>{entity}</div>
                <div style="margin-top:0.55rem;">
                    {risk}
                    {verification}
                </div>
                <div class="case-meta">
                    Case {case_id} |
                    Review status: {review_status} |
                    Overseas: {overseas} |
                    Received: {created_at}
                </div>
            </div>
            """.format(
                title=title,
                entity=entity,
                risk=risk_badge(
                    case.get("risk_level")
                ),
                verification=verification_badge(
                    case.get("verification_status")
                ),
                case_id=case_id,
                review_status=format_review_status(
                    case.get("review_status")
                ),
                overseas=format_boolean(
                    case.get("is_overseas")
                ),
                created_at=format_datetime(
                    case.get("created_at")
                ),
            ),
            unsafe_allow_html=True,
        )

    with action_column:
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
        cases = client.get_cases(
            risk_level=filters["risk_level"],
            review_status=filters["review_status"],
            is_overseas=filters["is_overseas"],
            limit=filters["limit"],
        )
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
                <p>
                    No referred cases match the selected filters.
                </p>
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
            "This case has already been resolved. "
            "The recorded decision cannot be edited."
        )

        show_detail(
            "Recorded outcome",
            format_outcome(review_outcome),
        )

        show_detail(
            "Reviewer notes",
            case.get("review_notes"),
        )

        show_detail(
            "Reviewed at",
            format_datetime(case.get("reviewed_at")),
        )

        return

    outcome_values = [
        outcome.value
        for outcome in ReviewOutcome
    ]

    outcome = st.selectbox(
        "Outcome",
        options=outcome_values,
        format_func=format_outcome,
        index=None,
        placeholder="Select a reviewer outcome",
    )

    reviewer = st.text_input(
        "Reviewer name",
        placeholder="Enter the reviewer name",
        help=(
            "Temporary demonstration field. "
            "Reviewer identity will later come from authentication."
        ),
    )

    notes = st.text_area(
        "Decision notes",
        placeholder=(
            "Record the evidence considered and explain "
            "the reason for the decision."
        ),
        height=140,
    )

    st.caption(
        "Decisions are recorded by the backend and cannot be edited."
    )

    submit_disabled = (
        not outcome
        or not reviewer.strip()
        or not notes.strip()
    )

    if st.button(
        "Submit decision",
        type="primary",
        disabled=submit_disabled,
        use_container_width=True,
    ):
        try:
            with st.spinner("Recording reviewer decision..."):
                client.submit_decision(
                    case_id=case_id,
                    outcome=outcome,
                    notes=notes,
                    reviewer=reviewer,
                )

            st.success("The reviewer decision was recorded.")

            st.session_state[
                "decision_success_message"
            ] = "The reviewer decision was recorded."

            st.rerun()

        except SafeHireAPIError as error:
            st.error(error.message)

        except ValueError as error:
            st.error(str(error))
            
def render_case_detail(client, case_id):
    if st.button("Back to queue"):
        st.session_state.selected_case_id = None
        st.rerun()

    try:
        case = client.get_case(case_id)
    except SafeHireAPIError as error:
        st.error(error.message)
        return

    st.subheader(
        "Case {}".format(
            display_value(case.get("case_id"))
        )
    )

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
            verification_badge(
                case.get("verification_status")
            ),
            unsafe_allow_html=True,
        )

    st.divider()

    left_column, right_column = st.columns(2)

    with left_column:
        with st.container(border=True):
            st.markdown("### Case information")

            show_detail(
                "Posting title",
                case.get("title"),
            )

            show_detail(
                "Entity",
                case.get("entity_name"),
            )

            show_detail(
                "Review status",
                format_review_status(
                    case.get("review_status")
                ),
            )

            show_detail(
                "Created",
                format_datetime(
                    case.get("created_at")
                ),
            )

            show_detail(
                "Overseas posting",
                format_boolean(
                    case.get("is_overseas")
                ),
            )

    with right_column:
        with st.container(border=True):
            st.markdown("### Posting details")

            show_detail(
                "Location",
                case.get("location"),
            )

            show_detail(
                "Destination country",
                case.get("destination_country"),
            )

            show_detail(
                "Salary",
                case.get("salary_text"),
            )

            show_detail(
                "Contact email",
                case.get("contact_email"),
            )

            show_detail(
                "Model probability",
                format_probability(
                    case.get("probability")
                ),
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
                reason_text = display_value(
                    reason.get("text")
                )
                reason_code = display_value(
                    reason.get("code")
                )
                reason_source = display_value(
                    reason.get("source")
                )

                with st.container(border=True):
                    st.write(reason_text)
                    st.caption(
                        "Code: {} | Source: {}".format(
                            reason_code,
                            reason_source,
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

    selected_case_id = st.session_state.selected_case_id

    if selected_case_id:
        render_case_detail(
            client,
            selected_case_id,
        )
    else:
        render_statistics(client)
        st.write("")
        render_queue(client, filters)


if __name__ == "__main__":
    main()