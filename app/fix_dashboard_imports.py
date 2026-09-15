"""Fix Hakiki Hire Streamlit imports after the analytics/report upgrade.

Run from the job-scam-detection repository root:
    python fix_dashboard_imports.py
"""

from __future__ import annotations

import ast
import shutil
from pathlib import Path

APP = Path("app/government/app.py")
ANALYTICS = Path("app/government/analytics.py")
BACKUP = Path("app/government/app.py.before-import-fix")

REQUIRED_ANALYTICS_FUNCTIONS = {
    "render_overview_analytics",
    "render_report_analytics",
    "render_report_summary",
}

IMPORT_BLOCK = '''from analytics import (
    render_overview_analytics,
    render_report_analytics,
    render_report_summary,
)
from api_client import HakikiHireAPIClient, HakikiHireAPIError
from report_generator import generate_summary_report_pdf, report_filename

'''


def function_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def main() -> int:
    if not APP.is_file() or not ANALYTICS.is_file():
        print("ERROR: Run this script from the job-scam-detection repository root.")
        return 1

    available = function_names(ANALYTICS)
    missing = sorted(REQUIRED_ANALYTICS_FUNCTIONS - available)
    if missing:
        print("ERROR: analytics.py is not the upgraded version.")
        print("Missing functions:", ", ".join(missing))
        print("Replace app/government/analytics.py first, then rerun this script.")
        return 1

    source = APP.read_text(encoding="utf-8")
    start_marker = "from src.core.schemas import ReviewOutcome\n"
    end_marker = "LOCAL_API_URL ="
    start = source.find(start_marker)
    end = source.find(end_marker)
    if start < 0 or end < 0 or end <= start:
        print("ERROR: Could not locate the import section in app.py.")
        return 1

    start += len(start_marker)
    corrected = source[:start] + "\n" + IMPORT_BLOCK + source[end:]

    required_calls = {
        "render_overview_analytics(cases)",
        "render_report_summary(cases)",
        "render_report_analytics(cases)",
    }
    absent_calls = sorted(item for item in required_calls if item not in corrected)
    if absent_calls:
        print("ERROR: app.py Reports upgrade is incomplete.")
        print("Missing calls:", ", ".join(absent_calls))
        return 1

    try:
        compile(corrected, str(APP), "exec")
    except Exception as error:
        print("ERROR: Corrected app.py did not compile:", error)
        return 1

    shutil.copy2(APP, BACKUP)
    APP.write_text(corrected, encoding="utf-8")

    print("UPDATED:", APP)
    print("BACKUP:", BACKUP)
    print("Streamlit now uses direct sibling imports.")
    print("Overview and Reports analytics imports are aligned.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
