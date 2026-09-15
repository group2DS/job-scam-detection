"""Upgrade the Hakiki Hire Streamlit Reports page without replacing app.py.

Run from the job-scam-detection repository root:
    python upgrade_reports_ui.py
"""

from __future__ import annotations

import shutil
from pathlib import Path

PATH = Path("app/government/app.py")
BACKUP = Path("app/government/app.py.before-reports-ui")


def main() -> int:
    if not PATH.is_file():
        print("ERROR: Run this file from the job-scam-detection repository root.")
        return 1

    original = PATH.read_text(encoding="utf-8")
    updated = original

    updated = updated.replace(
        "from app.government.analytics import render_filtered_queue_analytics",
        "from app.government.analytics import (\n"
        "        render_overview_analytics,\n"
        "        render_report_analytics,\n"
        "        render_report_summary,\n"
        "    )",
        1,
    )
    updated = updated.replace(
        "from analytics import render_filtered_queue_analytics",
        "from analytics import (\n"
        "        render_overview_analytics,\n"
        "        render_report_analytics,\n"
        "        render_report_summary,\n"
        "    )",
        1,
    )
    updated = updated.replace(
        "    render_filtered_queue_analytics(cases)\n",
        "    render_overview_analytics(cases)\n",
        1,
    )

    start = updated.find("def render_reports(")
    end = updated.find("\ndef render_access_management(", start)
    if start < 0 or end < 0:
        print("ERROR: Could not find render_reports() in app.py.")
        return 1

    replacement = '''def render_reports(
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
'''
    updated = updated[:start] + replacement + updated[end:]

    required = [
        "render_overview_analytics(cases)",
        "render_report_summary(cases)",
        "render_report_analytics(cases)",
        "Hakiki Hire Intelligence Report",
    ]
    missing = [item for item in required if item not in updated]
    if missing:
        print("ERROR: Upgrade incomplete:", missing)
        return 1

    try:
        compile(updated, str(PATH), "exec")
    except Exception as error:
        print("ERROR: Updated app.py did not compile:", error)
        return 1

    shutil.copy2(PATH, BACKUP)
    PATH.write_text(updated, encoding="utf-8")
    print("UPDATED:", PATH)
    print("BACKUP:", BACKUP)
    print("Overview and Reports now use different KPIs and visualizations.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
