"""Authentication and protected-route tests for SafeHire."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.api.main import app
from src.core.security import create_access_token, hash_password
from src.db.models import Base, ReviewCase, User, get_session


TEST_DATABASE_URL = "sqlite+pysqlite:///:memory:"
TEST_PASSWORD = "StrongPassword123!"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    future=True,
)
TestingSessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


def override_get_session() -> Generator[Session, None, None]:
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


app.dependency_overrides[get_session] = override_get_session
client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_database() -> Generator[None, None, None]:
    """Recreate the isolated database before every test."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    session = TestingSessionLocal()
    try:
        session.add(
            User(
                username="admin",
                password_hash=hash_password(TEST_PASSWORD),
                display_name="SafeHire Administrator",
                role="admin",
                is_active=True,
            )
        )
        session.add(
            User(
                username="inactive",
                password_hash=hash_password(TEST_PASSWORD),
                display_name="Inactive Reviewer",
                role="reviewer",
                is_active=False,
            )
        )
        session.add(
            ReviewCase(
                case_id="C-TEST01",
                title="Synthetic test posting",
                description="Synthetic posting used only for automated tests.",
                entity_name="Example Organisation",
                entity_type="company",
                location="Nairobi",
                destination_country=None,
                is_overseas=False,
                salary_text=None,
                contact_email=None,
                contact_phone=None,
                source_url=None,
                risk_level="high_risk",
                verification_status="unverified",
                probability=0.91,
                model_version="test-model",
                review_status="open",
            )
        )
        session.commit()
    finally:
        session.close()

    yield


def login(
    username: str = "admin",
    password: str = TEST_PASSWORD,
):
    return client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )


def bearer_headers() -> dict[str, str]:
    response = login()
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": "Bearer {}".format(token)}


def decision_payload(
    outcome: str = "confirmed_scam",
    notes: str = "Synthetic automated test decision.",
) -> dict[str, str]:
    return {
        "outcome": outcome,
        "notes": notes,
        "reviewer": "Ignored Browser Value",
    }


def test_successful_login_returns_token_and_profile():
    response = login()

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["reviewer"]["username"] == "admin"
    assert body["reviewer"]["display_name"] == "SafeHire Administrator"
    assert body["reviewer"]["role"] == "admin"
    assert body["reviewer"]["is_active"] is True


def test_invalid_password_is_rejected():
    response = login(password="IncorrectPassword123!")

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password."


def test_unknown_username_is_rejected():
    response = login(username="missing-reviewer")

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password."


def test_inactive_reviewer_is_rejected():
    response = login(username="inactive")

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password."


def test_auth_me_requires_bearer_token():
    assert client.get("/api/auth/me").status_code == 401


def test_auth_me_rejects_invalid_token():
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401


def test_auth_me_rejects_expired_token():
    token = create_access_token(
        user_id=1,
        username="admin",
        display_name="SafeHire Administrator",
        role="admin",
        expires_minutes=-1,
    )

    response = client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer {}".format(token)},
    )

    assert response.status_code == 401


def test_auth_me_returns_current_reviewer():
    response = client.get(
        "/api/auth/me",
        headers=bearer_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "admin"
    assert body["display_name"] == "SafeHire Administrator"
    assert body["role"] == "admin"
    assert body["is_active"] is True


@pytest.mark.parametrize(
    "method,path,payload",
    [
        ("get", "/api/cases", None),
        ("get", "/api/cases/stats", None),
        ("get", "/api/cases/C-TEST01", None),
        (
            "post",
            "/api/cases/C-TEST01/decision",
            decision_payload(),
        ),
    ],
)
def test_government_routes_require_authentication(
    method,
    path,
    payload,
):
    if method == "post":
        response = client.post(path, json=payload)
    else:
        response = client.get(path)

    assert response.status_code == 401


def test_authenticated_reviewer_can_list_cases():
    response = client.get("/api/cases", headers=bearer_headers())

    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert any(case["case_id"] == "C-TEST01" for case in response.json())


def test_authenticated_reviewer_can_view_statistics():
    response = client.get(
        "/api/cases/stats",
        headers=bearer_headers(),
    )

    assert response.status_code == 200
    assert isinstance(response.json(), dict)


def test_authenticated_reviewer_can_view_case_detail():
    response = client.get(
        "/api/cases/C-TEST01",
        headers=bearer_headers(),
    )

    assert response.status_code == 200
    assert response.json()["case_id"] == "C-TEST01"


def test_authenticated_reviewer_can_submit_decision():
    response = client.post(
        "/api/cases/C-TEST01/decision",
        headers=bearer_headers(),
        json=decision_payload(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["review_status"] == "resolved"
    assert body["review_outcome"] == "confirmed_scam"


def test_decision_is_persisted_with_authenticated_reviewer():
    response = client.post(
        "/api/cases/C-TEST01/decision",
        headers=bearer_headers(),
        json=decision_payload(),
    )
    assert response.status_code == 200

    session = TestingSessionLocal()
    try:
        case = session.scalar(
            select(ReviewCase).where(ReviewCase.case_id == "C-TEST01")
        )
        assert case is not None
        assert case.review_status == "resolved"
        assert case.review_outcome == "confirmed_scam"
        assert case.reviewer == "SafeHire Administrator"
        assert case.audit_entries
        assert case.audit_entries[-1].actor == "admin"
    finally:
        session.close()


def test_needs_more_evidence_resolves_case():
    notes = "Additional registry documentation is required."
    response = client.post(
        "/api/cases/C-TEST01/decision",
        headers=bearer_headers(),
        json=decision_payload(
            outcome="needs_more_evidence",
            notes=notes,
        ),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["review_status"] == "resolved"
    assert body["review_outcome"] == "needs_more_evidence"
    assert body["review_notes"] == notes


def test_needs_more_evidence_cannot_be_replaced():
    first_response = client.post(
        "/api/cases/C-TEST01/decision",
        headers=bearer_headers(),
        json=decision_payload(
            outcome="needs_more_evidence",
            notes="Additional evidence is required.",
        ),
    )
    assert first_response.status_code == 200

    second_response = client.post(
        "/api/cases/C-TEST01/decision",
        headers=bearer_headers(),
        json=decision_payload(
            outcome="confirmed_scam",
            notes="Attempted replacement decision.",
        ),
    )

    assert second_response.status_code == 409
    assert second_response.json()["detail"] == (
        "This case has already been resolved and cannot be edited."
    )


def test_health_endpoint_remains_public():
    assert client.get("/api/health").status_code == 200


def test_analysis_formats_endpoint_remains_public():
    response = client.get("/api/analyse/formats")
    assert response.status_code != 401
