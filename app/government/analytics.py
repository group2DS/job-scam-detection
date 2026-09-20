"""Presentation-quality analytics for the Hakiki Hire Government Dashboard.

Overview visualizations monitor the live queue. Report visualizations focus on
final outcomes, verification exposure, review completion, and intelligence.
The module is independent of app.py and the API client to avoid circular imports.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, Iterable, List

import altair as alt
import pandas as pd
import streamlit as st

NAVY = "#071F33"
BLUE = "#0A6A96"
CYAN = "#38BDF8"
GREEN = "#22C55E"
AMBER = "#F59E0B"
ORANGE = "#F97316"
RED = "#EF4444"
SLATE = "#64748B"
LIGHT = "#E2E8F0"

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
STATUS_LABELS = {"open": "Open", "resolved": "Resolved"}
OUTCOME_LABELS = {
    "confirmed_legitimate": "Confirmed legitimate",
    "confirmed_scam": "Confirmed scam",
    "needs_more_evidence": "Needs more evidence",
    "duplicate": "Duplicate report",
}
RISK_DOMAIN = ["Lower risk", "Suspicious", "High risk"]
RISK_RANGE = [GREEN, AMBER, RED]
VERIFICATION_DOMAIN = [
    "Verified",
    "Unverified",
    "Blacklisted",
    "Possible impersonation",
    "Not applicable",
]
VERIFICATION_RANGE = [GREEN, AMBER, RED, ORANGE, SLATE]
OUTCOME_DOMAIN = [
    "Confirmed legitimate",
    "Confirmed scam",
    "Needs more evidence",
    "Duplicate report",
    "Not yet decided",
]
OUTCOME_RANGE = [GREEN, RED, AMBER, SLATE, LIGHT]


def _display(value: Any, fallback: str = "Not provided") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    if not text or text.lower() in {"none", "null", "nan"}:
        return fallback
    return text


def _label(mapping: Dict[str, str], value: Any, fallback: str) -> str:
    raw = _display(value, fallback)
    if raw == fallback:
        return fallback
    return mapping.get(raw, raw.replace("_", " ").strip().capitalize())


def cases_dataframe(cases: Iterable[Dict[str, Any]]) -> pd.DataFrame:
    """Convert filtered case dictionaries into a chart-ready dataframe."""
    rows: List[Dict[str, Any]] = []
    for case in cases:
        if not isinstance(case, dict):
            continue
        created = pd.to_datetime(case.get("created_at"), errors="coerce", utc=True)
        reviewed = pd.to_datetime(case.get("reviewed_at"), errors="coerce", utc=True)
        rows.append(
            {
                "case_id": _display(case.get("case_id"), "Unknown case"),
                "title": _display(case.get("title"), "Title not provided"),
                "entity": _display(case.get("entity_name"), "Entity not provided"),
                "created_at": created,
                "created_day": created.floor("D") if not pd.isna(created) else pd.NaT,
                "reviewed_at": reviewed,
                "reviewed_day": reviewed.floor("D") if not pd.isna(reviewed) else pd.NaT,
                "risk": _label(RISK_LABELS, case.get("risk_level"), "Not provided"),
                "verification": _label(
                    VERIFICATION_LABELS,
                    case.get("verification_status"),
                    "Not provided",
                ),
                "status": _label(STATUS_LABELS, case.get("review_status"), "Not provided"),
                "outcome": _label(
                    OUTCOME_LABELS,
                    case.get("review_outcome"),
                    "Not yet decided",
                ),
                "country": _display(
                    case.get("destination_country"),
                    "Local or not provided",
                ),
                "reviewer": _display(case.get("reviewer"), "Not provided"),
                "is_overseas": case.get("is_overseas") is True,
            }
        )
    return pd.DataFrame(rows)


def _card(title: str, caption: str):
    container = st.container(border=True)
    container.markdown("#### {}".format(title))
    container.caption(caption)
    return container


def _base_chart(chart: alt.Chart, height: int = 300) -> alt.Chart:
    return (
        chart.properties(height=height)
        .configure_view(strokeWidth=0)
        .configure_axis(
            labelColor="#334155",
            titleColor="#334155",
            gridColor="#E8EEF4",
            domainColor="#B8C5D1",
            tickColor="#B8C5D1",
            labelFontSize=11,
            titleFontSize=12,
        )
        .configure_legend(
            labelColor="#334155",
            titleColor="#334155",
            orient="bottom",
        )
    )


def _count_frame(frame: pd.DataFrame, field: str, label: str) -> pd.DataFrame:
    return frame[field].value_counts().rename_axis(label).reset_index(name="Cases")


def _donut(
    frame: pd.DataFrame,
    field: str,
    title: str,
    domain: List[str],
    color_range: List[str],
) -> None:
    counts = _count_frame(frame, field, title)
    total = int(counts["Cases"].sum())
    chart = (
        alt.Chart(counts)
        .mark_arc(innerRadius=72, outerRadius=112, stroke="white", strokeWidth=3)
        .encode(
            theta=alt.Theta("Cases:Q"),
            color=alt.Color(
                "{}:N".format(title),
                scale=alt.Scale(domain=domain, range=color_range),
                legend=alt.Legend(title=None, columns=1),
            ),
            tooltip=[
                alt.Tooltip("{}:N".format(title), title=title),
                alt.Tooltip("Cases:Q"),
            ],
        )
    )
    center = (
        alt.Chart(pd.DataFrame({"label": ["{}\nTotal".format(total)]}))
        .mark_text(fontSize=18, fontWeight="bold", color=NAVY, lineBreak="\n")
        .encode(text="label:N")
    )
    st.altair_chart(_base_chart(chart + center, 300), width="stretch")


def _horizontal_bar(
    frame: pd.DataFrame,
    field: str,
    category_title: str,
    color: str,
    maximum: int = 10,
) -> None:
    counts = _count_frame(frame, field, category_title).head(maximum)
    if counts.empty:
        st.info("No matching records are available for this chart.")
        return
    bars = (
        alt.Chart(counts)
        .mark_bar(cornerRadiusEnd=7, color=color)
        .encode(
            y=alt.Y(
                "{}:N".format(category_title),
                sort="-x",
                title=None,
                axis=alt.Axis(labelLimit=220),
            ),
            x=alt.X("Cases:Q", title="Cases", axis=alt.Axis(tickMinStep=1)),
            tooltip=[alt.Tooltip("{}:N".format(category_title)), "Cases:Q"],
        )
    )
    labels = bars.mark_text(
        align="left",
        baseline="middle",
        dx=6,
        color=NAVY,
        fontWeight="bold",
    ).encode(text="Cases:Q")
    height = max(260, min(410, 42 * len(counts)))
    st.altair_chart(_base_chart(bars + labels, height), width="stretch")


def _queue_trend(frame: pd.DataFrame) -> None:
    dated = frame.dropna(subset=["created_day"])
    if dated.empty:
        st.info("No dated cases are available for the queue trend.")
        return
    trend = (
        dated.groupby(["created_day", "risk"], as_index=False)
        .size()
        .rename(columns={"size": "Cases"})
    )
    chart = (
        alt.Chart(trend)
        .mark_area(opacity=0.22, line={"strokeWidth": 3}, point={"size": 45})
        .encode(
            x=alt.X("created_day:T", title="Referral date", axis=alt.Axis(format="%d %b")),
            y=alt.Y("Cases:Q", title="Cases", axis=alt.Axis(tickMinStep=1)),
            color=alt.Color(
                "risk:N",
                title="Risk level",
                scale=alt.Scale(domain=RISK_DOMAIN, range=RISK_RANGE),
            ),
            tooltip=[
                alt.Tooltip("created_day:T", title="Date", format="%d %b %Y"),
                alt.Tooltip("risk:N", title="Risk"),
                "Cases:Q",
            ],
        )
    )
    st.altair_chart(_base_chart(chart, 325), width="stretch")


def _verification_chart(frame: pd.DataFrame) -> None:
    counts = _count_frame(frame, "verification", "Verification status")
    bars = (
        alt.Chart(counts)
        .mark_bar(cornerRadiusEnd=7)
        .encode(
            y=alt.Y("Verification status:N", sort="-x", title=None),
            x=alt.X("Cases:Q", title="Cases", axis=alt.Axis(tickMinStep=1)),
            color=alt.Color(
                "Verification status:N",
                legend=None,
                scale=alt.Scale(
                    domain=VERIFICATION_DOMAIN,
                    range=VERIFICATION_RANGE,
                ),
            ),
            tooltip=["Verification status:N", "Cases:Q"],
        )
    )
    labels = bars.mark_text(
        align="left", baseline="middle", dx=6, color=NAVY, fontWeight="bold"
    ).encode(text="Cases:Q")
    st.altair_chart(_base_chart(bars + labels, 300), width="stretch")


def _resolution_progress(frame: pd.DataFrame) -> None:
    total = len(frame)
    resolved = int((frame["status"] == "Resolved").sum())
    open_cases = total - resolved
    progress = resolved / total if total else 0.0
    st.markdown(
        "<div style='font-size:2.1rem;font-weight:800;color:{}'>{:.1f}%</div>"
        "<div style='color:#64748b;margin-bottom:.65rem'>Resolution rate</div>".format(
            NAVY, progress * 100
        ),
        unsafe_allow_html=True,
    )
    st.progress(progress)
    first, second = st.columns(2)
    first.metric("Resolved", resolved)
    second.metric("Open", open_cases)


def render_overview_analytics(cases: Iterable[Dict[str, Any]]) -> None:
    """Render operational monitoring charts for the current review queue."""
    frame = cases_dataframe(cases)
    if frame.empty:
        st.info("No cases are available for Overview analytics.")
        return

    country_column, risk_column = st.columns([1.65, 1], gap="large")
    with country_column:
        with _card(
            "Cases by destination",
            "All cases in the current queue scope, ranked by destination",
        ):
            _horizontal_bar(frame, "country", "Destination", BLUE)
    with risk_column:
        with _card("Risk distribution", "Current model-risk composition"):
            _donut(frame, "risk", "Risk level", RISK_DOMAIN, RISK_RANGE)

    trend_column, verification_column = st.columns([1.65, 1], gap="large")
    with trend_column:
        with _card("Incoming case trend", "Daily referrals grouped by risk"):
            _queue_trend(frame)
    with verification_column:
        with _card("Verification status", "Current integrity and identity findings"):
            _verification_chart(frame)

    with _card("Review progress", "Completion of the current filtered queue"):
        _resolution_progress(frame)


def _report_metrics(
    frame: pd.DataFrame,
) -> Dict[str, Any]:
    """Return complete decision KPIs for the reporting scope."""

    total = len(frame)
    resolved_mask = frame["status"] == "Resolved"
    resolved = int(resolved_mask.sum())

    confirmed_legitimate = int(
        (
            frame["outcome"]
            == "Confirmed legitimate"
        ).sum()
    )
    confirmed_scams = int(
        (
            frame["outcome"]
            == "Confirmed scam"
        ).sum()
    )
    needs_more_evidence = int(
        (
            frame["outcome"]
            == "Needs more evidence"
        ).sum()
    )
    duplicates = int(
        (
            frame["outcome"]
            == "Duplicate report"
        ).sum()
    )
    verified_but_suspicious = int(
        (
            frame["outcome"]
            == "Verified but suspicious"
        ).sum()
    )

    recognized = (
        confirmed_legitimate
        + confirmed_scams
        + needs_more_evidence
        + duplicates
        + verified_but_suspicious
    )

    other_resolutions = max(
        0,
        resolved - recognized,
    )

    return {
        "Total analysed": total,
        "Confirmed legitimate": confirmed_legitimate,
        "Confirmed scams": confirmed_scams,
        "Needs more evidence": needs_more_evidence,
        "Duplicate reports": duplicates,
        "Verified but suspicious": verified_but_suspicious,
        "Other resolutions": other_resolutions,
        "Resolution rate": "{:.1f}%".format(
            (resolved / total * 100)
            if total
            else 0
        ),
    }

def render_report_summary(cases: Iterable[Dict[str, Any]]) -> None:
    """Render outcome-focused KPIs for the Reports page."""
    frame = cases_dataframe(cases)
    metrics = _report_metrics(frame)
    columns = st.columns(8)
    for column, (label, value) in zip(columns, metrics.items()):
        column.metric(label, value)


def _decision_trend(frame: pd.DataFrame) -> None:
    resolved = frame[
        frame["reviewed_day"].notna()
        & frame["outcome"].isin(OUTCOME_DOMAIN[:-1])
    ]
    if resolved.empty:
        st.info("Reviewed dates are not available for a decision trend.")
        return
    trend = (
        resolved.groupby(["reviewed_day", "outcome"], as_index=False)
        .size()
        .rename(columns={"size": "Decisions"})
    )
    chart = (
        alt.Chart(trend)
        .mark_area(opacity=0.18, line={"strokeWidth": 3}, point={"size": 52})
        .encode(
            x=alt.X("reviewed_day:T", title="Decision date", axis=alt.Axis(format="%d %b")),
            y=alt.Y("Decisions:Q", title="Decisions", axis=alt.Axis(tickMinStep=1)),
            color=alt.Color(
                "outcome:N",
                title="Final outcome",
                scale=alt.Scale(domain=OUTCOME_DOMAIN, range=OUTCOME_RANGE),
            ),
            tooltip=[
                alt.Tooltip("reviewed_day:T", title="Date", format="%d %b %Y"),
                alt.Tooltip("outcome:N", title="Outcome"),
                "Decisions:Q",
            ],
        )
    )
    st.altair_chart(_base_chart(chart, 340), width="stretch")


def _risk_outcome_chart(frame: pd.DataFrame) -> None:
    grouped = (
        frame.groupby(["risk", "outcome"], as_index=False)
        .size()
        .rename(columns={"size": "Cases"})
    )
    chart = (
        alt.Chart(grouped)
        .mark_bar(cornerRadiusEnd=5)
        .encode(
            y=alt.Y("risk:N", title=None, sort=RISK_DOMAIN[::-1]),
            x=alt.X("Cases:Q", title="Cases", stack="zero"),
            color=alt.Color(
                "outcome:N",
                title="Final outcome",
                scale=alt.Scale(domain=OUTCOME_DOMAIN, range=OUTCOME_RANGE),
            ),
            tooltip=[
                alt.Tooltip("risk:N", title="Risk"),
                alt.Tooltip("outcome:N", title="Outcome"),
                "Cases:Q",
            ],
        )
    )
    st.altair_chart(_base_chart(chart, 280), width="stretch")


def _key_findings(frame: pd.DataFrame) -> List[str]:
    total = len(frame)
    if total == 0:
        return ["No cases matched the current reporting scope."]
    scams = int((frame["outcome"] == "Confirmed scam").sum())
    blacklisted = int((frame["verification"] == "Blacklisted").sum())
    impersonation = int((frame["verification"] == "Possible impersonation").sum())
    resolved = int((frame["status"] == "Resolved").sum())
    findings = [
        "{} of {} analysed cases were confirmed scams ({:.1f}%).".format(
            scams, total, scams / total * 100
        ),
        "{} cases were blacklisted and {} were marked as possible impersonation.".format(
            blacklisted, impersonation
        ),
        "{} of {} cases were resolved ({:.1f}%).".format(
            resolved, total, resolved / total * 100
        ),
    ]
    scam_countries = frame[frame["outcome"] == "Confirmed scam"]["country"]
    if not scam_countries.empty:
        counts = scam_countries.value_counts()
        findings.append(
            "{} had the highest confirmed-scam volume with {} case{}.".format(
                counts.index[0], int(counts.iloc[0]), "" if counts.iloc[0] == 1 else "s"
            )
        )
    risk_counts = frame["risk"].value_counts()
    if not risk_counts.empty:
        findings.append(
            "{} was the most common risk category with {} case{}.".format(
                risk_counts.index[0],
                int(risk_counts.iloc[0]),
                "" if risk_counts.iloc[0] == 1 else "s",
            )
        )
    return findings


def _report_register(frame: pd.DataFrame) -> None:
    register = frame[
        [
            "case_id",
            "title",
            "entity",
            "country",
            "risk",
            "verification",
            "status",
            "outcome",
            "reviewer",
            "reviewed_at",
        ]
    ].copy()
    register.columns = [
        "Case ID",
        "Posting",
        "Entity",
        "Destination",
        "Risk",
        "Verification",
        "Status",
        "Final outcome",
        "Reviewer",
        "Reviewed date",
    ]
    register["Reviewed date"] = register["Reviewed date"].apply(
        lambda value: "Not provided"
        if pd.isna(value)
        else value.strftime("%d %b %Y %H:%M")
    )
    st.dataframe(register, hide_index=True, width="stretch", height=360)


def render_report_analytics(cases: Iterable[Dict[str, Any]]) -> None:
    """Render decision intelligence that is distinct from Overview."""
    frame = cases_dataframe(cases)
    if frame.empty:
        st.info("No cases match the current reporting scope.")
        return

    outcome_column, country_column = st.columns([1, 1.45], gap="large")
    with outcome_column:
        with _card("Decision outcomes", "Final decisions and unresolved cases"):
            _donut(frame, "outcome", "Final outcome", OUTCOME_DOMAIN, OUTCOME_RANGE)
    with country_column:
        with _card(
            "Confirmed scams by destination",
            "Only cases whose final outcome is Confirmed scam",
        ):
            scams = frame[frame["outcome"] == "Confirmed scam"]
            _horizontal_bar(scams, "country", "Destination", RED)

    with _card("Decision trend", "Final outcomes recorded over time"):
        _decision_trend(frame)

    exposure_column, completion_column = st.columns([1.45, 1], gap="large")
    with exposure_column:
        with _card(
            "Verification exposure",
            "Blacklisting, impersonation, verification, and unresolved exposure",
        ):
            _verification_chart(frame)
    with completion_column:
        with _card("Review completion", "Resolved versus open cases"):
            _resolution_progress(frame)

    with _card(
        "Risk level versus final outcome",
        "Comparison of initial risk classification and reviewer decisions",
    ):
        _risk_outcome_chart(frame)

    with _card("Key findings", "Calculated from the current reporting scope"):
        for finding in _key_findings(frame):
            st.markdown("- {}".format(finding))

    watchlist = frame[
        frame["verification"].isin(["Blacklisted", "Possible impersonation"])
    ]
    with _card(
        "Blacklist and impersonation watchlist",
        "Cases requiring focused integrity attention",
    ):
        if watchlist.empty:
            st.info("No watchlist cases match the current reporting scope.")
        else:
            st.dataframe(
                watchlist[
                    ["case_id", "entity", "title", "verification", "country", "outcome"]
                ].rename(
                    columns={
                        "case_id": "Case ID",
                        "entity": "Entity",
                        "title": "Posting",
                        "verification": "Verification",
                        "country": "Destination",
                        "outcome": "Outcome",
                    }
                ),
                hide_index=True,
                width="stretch",
            )

    with _card("Complete report register", "All cases in the current report scope"):
        _report_register(frame)


def render_filtered_queue_analytics(cases: Iterable[Dict[str, Any]]) -> None:
    """Backward-compatible wrapper for the operational Overview charts."""
    render_overview_analytics(cases)
