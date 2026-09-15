"""Run Hakiki Hire branding, import, route, and test-suite checks.

Run from the job-scam-detection repository root:
    python test_hakiki_hire_integration.py

This script does not modify project files or start servers.
"""

from __future__ import annotations

import compileall
import importlib
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
SKIP_DIRS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".rebrand-backup",
    ".venv",
    "venv",
    "node_modules",
}
TEXT_SUFFIXES = {
    ".py", ".md", ".txt", ".toml", ".yaml", ".yml",
    ".json", ".ini", ".cfg", ".env", ".example",
}
REQUIRED_PATHS = [
    "app/government/app.py",
    "app/government/api_client.py",
    "app/government/analytics.py",
    "app/government/report_generator.py",
    "app/government/tests/test_api_client.py",
    "src/api/dependencies/auth.py",
    "src/api/routes/auth.py",
    "src/api/routes/cases.py",
    "src/api/main.py",
    "scripts/seed_admin.py",
    "tests/test_auth.py",
]
REQUIRED_AUTH_ROUTES = {
    "/api/auth/login",
    "/api/auth/me",
    "/api/auth/users",
    "/api/auth/users/{user_id}/status",
    "/api/auth/users/{user_id}/role",
}
REQUIRED_CASE_ROUTES = {
    "/api/cases",
    "/api/cases/stats",
    "/api/cases/countries",
    "/api/cases/{case_id}",
    "/api/cases/{case_id}/decision",
}
FAILURES: list[str] = []


def heading(value: str) -> None:
    print("\n" + "=" * 72)
    print(value)
    print("=" * 72)


def passed(value: str) -> None:
    print("PASS:", value)


def failed(value: str) -> None:
    FAILURES.append(value)
    print("FAIL:", value)


def is_skipped(path: Path) -> bool:
    return any(part in SKIP_DIRS for part in path.parts)


def text_files():
    roots = [ROOT / name for name in ("app", "src", "scripts", "tests")]
    for base in roots:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or is_skipped(path):
                continue
            # Do not scan this integration checker itself. Its source must
            # contain the legacy-name and markup patterns it is searching for.
            if path.resolve() == Path(__file__).resolve():
                continue
            if path.name in {".env", ".env.example"} or path.suffix.lower() in TEXT_SUFFIXES:
                yield path


def check_required_files() -> None:
    heading("1. Required files")
    for relative in REQUIRED_PATHS:
        path = ROOT / relative
        if path.is_file() and path.stat().st_size > 0:
            passed(relative)
        else:
            failed(f"Missing or empty: {relative}")


def check_branding() -> None:
    heading("2. Branding and markup")
    old_brand = []
    corrupt_markup = []
    for path in text_files():
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        lower = content.lower()
        if "safehire" in lower or "safe hire" in lower:
            old_brand.append(str(path.relative_to(ROOT)))
        if any(token in content for token in ("&lt;", "&gt;", "&quot;", "<a href=", "noopener")):
            corrupt_markup.append(str(path.relative_to(ROOT)))

    if old_brand:
        failed("Old branding remains in: " + ", ".join(sorted(old_brand)))
    else:
        passed("No SafeHire or Safe Hire branding in active text files")

    if corrupt_markup:
        failed("Corrupted chat markup remains in: " + ", ".join(sorted(corrupt_markup)))
    else:
        passed("No corrupted chat markup in active text files")


def check_python_compile() -> None:
    heading("3. Python compilation")
    success = True
    for folder in ("app", "src", "scripts", "tests"):
        target = ROOT / folder
        if target.exists():
            success = compileall.compile_dir(
                str(target),
                quiet=1,
                force=True,
            ) and success
    if success:
        passed("All Python files compile")
    else:
        failed("One or more Python files did not compile")


def check_imports() -> None:
    heading("4. Integration imports")
    sys.path.insert(0, str(ROOT))
    checks = [
        (
            "app.government.api_client",
            ["HakikiHireAPIClient", "HakikiHireAPIError"],
        ),
        (
            "app.government.analytics",
            ["render_filtered_queue_analytics"],
        ),
        (
            "app.government.report_generator",
            ["generate_summary_report_pdf", "report_filename"],
        ),
        (
            "src.api.dependencies.auth",
            ["get_current_user", "require_admin"],
        ),
    ]
    for module_name, attributes in checks:
        try:
            module = importlib.import_module(module_name)
        except Exception as error:
            failed(f"Import {module_name}: {type(error).__name__}: {error}")
            continue
        missing = [name for name in attributes if not hasattr(module, name)]
        if missing:
            failed(f"{module_name} is missing: {', '.join(missing)}")
        else:
            passed(f"{module_name}: {', '.join(attributes)}")


def check_fastapi_routes() -> None:
    heading("5. FastAPI routes")
    os.environ.setdefault(
        "JWT_SECRET_KEY",
        "hakiki-hire-integration-check-0123456789",
    )
    try:
        from src.api.main import app
        paths = set(app.openapi().get("paths", {}))
    except Exception as error:
        failed(f"FastAPI import/OpenAPI: {type(error).__name__}: {error}")
        return

    missing_auth = sorted(REQUIRED_AUTH_ROUTES - paths)
    missing_cases = sorted(REQUIRED_CASE_ROUTES - paths)
    if missing_auth:
        failed("Missing auth routes: " + ", ".join(missing_auth))
    else:
        passed("All authentication and access-management routes exist")
    if missing_cases:
        failed("Missing case routes: " + ", ".join(missing_cases))
    else:
        passed("All case and decision routes exist")


def run_pytest(label: str, target: str) -> None:
    heading(label)
    command = [sys.executable, "-m", "pytest", target, "-q"]
    print("RUN:", " ".join(command))
    result = subprocess.run(command, cwd=ROOT, check=False)
    if result.returncode == 0:
        passed(target)
    else:
        failed(f"pytest failed: {target}")


def main() -> int:
    if not (ROOT / "app" / "government").is_dir():
        print("Run this script from the job-scam-detection repository root.")
        return 2

    print("Hakiki Hire integration test runner")
    print("Repository:", ROOT)

    check_required_files()
    check_branding()
    check_python_compile()
    check_imports()
    check_fastapi_routes()

    if FAILURES:
        heading("Preflight result")
        print("Preflight failed. Pytest was not run because foundational checks failed.")
        for item in FAILURES:
            print(" -", item)
        return 1

    run_pytest(
        "6. Dashboard API-client tests",
        "app/government/tests/test_api_client.py",
    )
    run_pytest(
        "7. Authentication and access-management tests",
        "tests/test_auth.py",
    )

    heading("Final result")
    if FAILURES:
        print("HAKIKI HIRE INTEGRATION FAILED")
        for item in FAILURES:
            print(" -", item)
        return 1

    print("ALL HAKIKI HIRE PREFLIGHT AND AUTOMATED TESTS PASSED")
    print("Next manual check: start FastAPI and Streamlit, then verify login, filters, access management, case review, and PDF download.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
