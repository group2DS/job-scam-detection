"""Fix Hakiki Hire Streamlit logout and back-to-queue navigation.

Run from the job-scam-detection repository root:
    python fix_app_navigation.py
"""

from __future__ import annotations

import shutil
from pathlib import Path

PATH = Path("app/government/app.py")
BACKUP = Path("app/government/app.py.before-navigation-fix")


def main() -> int:
    if not PATH.is_file():
        print("ERROR: Run this file from the job-scam-detection repository root.")
        return 1

    original = PATH.read_text(encoding="utf-8")
    updated = original

    # Logout/session clearing must defer changing the widget-owned page key.
    updated = updated.replace(
        '    st.session_state.navigation_page = "Overview"\n',
        '    st.session_state.pending_navigation = "Overview"\n',
    )

    # Back to queue currently clears the selected case and reruns, but it must
    # also request Review queue for the next run.
    old_back_block = (
        '    if st.button("Back to review queue"):\n'
        '        st.session_state.selected_case_id = None\n'
        '        st.rerun()\n'
    )
    new_back_block = (
        '    if st.button("Back to review queue"):\n'
        '        st.session_state.selected_case_id = None\n'
        '        st.session_state.pending_navigation = "Review queue"\n'
        '        st.rerun()\n'
    )
    updated = updated.replace(old_back_block, new_back_block)

    # Apply deferred navigation before render_sidebar creates the radio widget.
    startup = (
        'def main() -> None:\n'
        '    apply_styles()\n'
        '    initialise_state()\n'
    )
    startup_with_pending = (
        'def main() -> None:\n'
        '    apply_styles()\n'
        '    initialise_state()\n\n'
        '    # Apply deferred navigation before the sidebar widget is created.\n'
        '    if "pending_navigation" in st.session_state:\n'
        '        st.session_state.navigation_page = st.session_state.pop(\n'
        '            "pending_navigation"\n'
        '        )\n'
    )
    if 'if "pending_navigation" in st.session_state:' not in updated:
        updated = updated.replace(startup, startup_with_pending, 1)

    required = [
        'st.session_state.pending_navigation = "Overview"',
        'st.session_state.pending_navigation = "Review queue"',
        'if "pending_navigation" in st.session_state:',
    ]
    missing = [item for item in required if item not in updated]
    if missing:
        print("ERROR: Could not apply all navigation changes:")
        for item in missing:
            print(" -", item)
        return 1

    # No direct page assignment is allowed outside the pending-value consumer.
    direct_assignments = [
        line.strip()
        for line in updated.splitlines()
        if "st.session_state.navigation_page =" in line
    ]
    expected = [
        'st.session_state.navigation_page = st.session_state.pop('
    ]
    if direct_assignments != expected:
        print("ERROR: Unsafe navigation_page assignments remain:")
        for line in direct_assignments:
            print(" -", line)
        return 1

    try:
        compile(updated, str(PATH), "exec")
    except Exception as error:
        print("ERROR: Corrected app.py did not compile:", error)
        return 1

    shutil.copy2(PATH, BACKUP)
    PATH.write_text(updated, encoding="utf-8")

    print("UPDATED:", PATH)
    print("BACKUP:", BACKUP)
    print("Logout target: Overview")
    print("Back button target: Review queue")
    print("Python syntax validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
