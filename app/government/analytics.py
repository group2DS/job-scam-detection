"""Dynamic analytics for the SafeHire Government Dashboard."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any, Iterable

import pandas as pd
import streamlit as st

try:
    from .formatters import (
        display_value,
        format_outcome,
        format_review_status,
        format_risk_level,
        format_verification_status,
    )
except ImportError:
    from formatters import (
        display_value,
        format_outcome,
        format_review_status,
        format_risk_level,
        format_verification_status,
    )
    
RISK_LABELS = {
    "lower_risk": "Lower risk",
    "suspicious": "Suspicious",
    "high_risk": "High risk",
}

STATUS_LABELS = {
    "open": "Open",
    "resolved": "Resolved",
}

MARKET_LABELS = {
    False: "Local",
    True: "Overseas",
}


def _parse_datetime(value: Any) -> datetime | None:
    """Convert an API date value into a datetime when possible."""
    if value is None:
        return None

    if isinstance(value, datetime):
        return value

    text = str(value).strip()
    if not text:
        return None

    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _count_frame(
    values: Iterable[Any],
    labels: dict[Any, str],
    index_name: str,
) -> pd.DataFrame:
    """Create a chart-ready count table with stable category ordering."""
    counts = Counter(values)
    rows = [
        {
            index_name: label,
            "Cases": counts.get(raw_value, 0),
        }
        for raw_value, label in labels.items()
    ]
    return pd.DataFrame(rows).set_index(index_name)


def build_daily_trend(
    cases: list[dict[str, Any]],
) -> pd.DataFrame:
    """Build daily case counts from the current filtered queue."""
    dates = []

    for case in cases:
        created_at = _parse_datetime(case.get("created_at"))
        if created_at is not None:
            dates.append(created_at.date())

    if not dates:
        return pd.DataFrame(columns=["Cases"])

    counts = Counter(dates)
    frame = pd.DataFrame(
        [
            {
                "Date": day,
                "Cases": count,
            }
            for day, count in sorted(counts.items())
        ]
    )
    return frame.set_index("Date")


def render_filtered_queue_analytics(
    cases: list[dict[str, Any]],
) -> None:
    """Render dynamic charts for the current filtered government queue."""
    st.markdown("## Queue trends and insights")
    st.caption(
        "Charts update from the current government review queue "
        "and selected filters."
    )

    if not cases:
        st.info("No cases are available for the selected filters.")
        return

    daily_trend = build_daily_trend(cases)
    risk_frame = _count_frame(
        (case.get("risk_level") for case in cases),
        RISK_LABELS,
        "Risk level",
    )
    status_frame = _count_frame(
        (case.get("review_status") for case in cases),
        STATUS_LABELS,
        "Review status",
    )
    market_frame = _count_frame(
        (case.get("is_overseas") for case in cases),
        MARKET_LABELS,
        "Market",
    )

    trend_column, risk_column = st.columns(
        [1.65, 1],
        gap="large",
    )

    with trend_column:
        with st.container(border=True):
            st.markdown("### Cases over time")
            if daily_trend.empty:
                st.info("No valid case dates are available.")
            else:
                st.line_chart(
                    daily_trend,
                    y="Cases",
                    color="#0a6a96",
                    width="stretch",
                )

    with risk_column:
        with st.container(border=True):
            st.markdown("### Risk distribution")
            st.bar_chart(
                risk_frame,
                y="Cases",
                color="#0a6a96",
                width="stretch",
            )

    status_column, market_column = st.columns(
        2,
        gap="large",
    )

    with status_column:
        with st.container(border=True):
            st.markdown("### Open versus resolved")
            st.bar_chart(
                status_frame,
                y="Cases",
                color="#15803d",
                width="stretch",
            )

    with market_column:
        with st.container(border=True):
            st.markdown("### Local versus overseas")
            st.bar_chart(
                market_frame,
                y="Cases",
                color="#b45309",
                width="stretch",
            )
