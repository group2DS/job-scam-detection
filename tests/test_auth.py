"""Authentication, reviewer workflow, and access-management tests for Hakiki Hire."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.api.main import app
from src.core.security import create_access_token, hash_password
from src.db.models import (
    Base,
    RegistryAuditEntry,
    RegistryRecord,
    ReviewCase,
    User,
    get_session,
)

TEST_DATABASE_URL = "sqlite+pysqlite:///:memory:"
TEST_PASSWORD = "StrongPassword123!"
ADMIN_DISPLAY_NAME = "Hakiki Hire Administrator"

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
    """Recreate and seed the isolated Hakiki Hire test database."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    session = TestingSessionLocal()
    try:
        session.add_all(
            [
                User(
                    username="admin",
                    password_hash=hash_password(TEST_PASSWORD),
                    display_name=ADMIN_DISPLAY_NAME,
                    role="admin",
                    is_active=True,
                ),
                User(
                    username="inactive",
                    password_hash=hash_password(TEST_PASSWORD),
                    display_name="Inactive Reviewer",
                    role="reviewer",
                    is_active=False,
                ),
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
                ),
            ]
        )
        session.commit()
    finally:
        session.close()

    yield


def login(username: str = "admin", password: str = TEST_PASSWORD):
    return client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )


def bearer_headers(
    username: str = "admin",
    password: str = TEST_PASSWORD,
) -> dict[str, str]:
    response = login(username=username, password=password)
    assert response.status_code == 200
    return {
        "Authorization": "Bearer {}".format(
            response.json()["access_token"]
        )
    }


def create_active_reviewer(
    username: str = "reviewer-one",
    display_name: str = "Reviewer One",
    password: str = TEST_PASSWORD,
) -> User:
    session = TestingSessionLocal()
    try:
        reviewer = User(
            username=username,
            password_hash=hash_password(password),
            display_name=display_name,
            role="reviewer",
            is_active=True,
        )
        session.add(reviewer)
        session.commit()
        session.refresh(reviewer)
        session.expunge(reviewer)
        return reviewer
    finally:
        session.close()


def decision_payload(
    outcome: str = "confirmed_scam",
    notes: str = "Synthetic automated test decision.",
) -> dict[str, str]:
    return {
        "outcome": outcome,
        "notes": notes,
        "reviewer": "Ignored Browser Value",
    }


# Login and profile


def test_successful_login_returns_token_and_profile():
    response = login()
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["reviewer"]["username"] == "admin"
    assert body["reviewer"]["display_name"] == ADMIN_DISPLAY_NAME
    assert body["reviewer"]["role"] == "admin"
    assert body["reviewer"]["is_active"] is True
    assert "password" not in body["reviewer"]
    assert "password_hash" not in body["reviewer"]


def test_login_normalizes_username():
    response = login(username="  ADMIN  ")
    assert response.status_code == 200
    assert response.json()["reviewer"]["username"] == "admin"


def test_invalid_password_is_rejected():
    response = login(password="IncorrectPassword123!")
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password."


def test_unknown_username_is_rejected():
    response = login(username="missing-reviewer")
    assert response.status_code == 401


def test_inactive_reviewer_is_rejected():
    response = login(username="inactive")
    assert response.status_code == 401


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
        display_name=ADMIN_DISPLAY_NAME,
        role="admin",
        expires_minutes=-1,
    )
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer {}".format(token)},
    )
    assert response.status_code == 401


def test_auth_me_returns_current_user_safely():
    response = client.get("/api/auth/me", headers=bearer_headers())
    assert response.status_code == 200
    body = response.json()
    assert body["display_name"] == ADMIN_DISPLAY_NAME
    assert body["role"] == "admin"
    assert "password" not in body
    assert "password_hash" not in body


# Protected case routes and reviewer attribution


@pytest.mark.parametrize(
    "method,path,payload",
    [
        ("get", "/api/cases", None),
        ("get", "/api/cases/stats", None),
        ("get", "/api/cases/countries", None),
        ("get", "/api/cases/C-TEST01", None),
        ("post", "/api/cases/C-TEST01/decision", decision_payload()),
    ],
)
def test_government_routes_require_authentication(method, path, payload):
    response = (
        client.post(path, json=payload)
        if method == "post"
        else client.get(path)
    )
    assert response.status_code == 401


def test_authenticated_user_can_list_cases():
    response = client.get("/api/cases", headers=bearer_headers())
    assert response.status_code == 200
    assert any(
        case["case_id"] == "C-TEST01"
        for case in response.json()
    )


def test_case_queue_accepts_verification_status_filter():
    response = client.get(
        "/api/cases",
        params={"verification_status": "unverified"},
        headers=bearer_headers(),
    )
    assert response.status_code == 200
    assert all(
        case["verification_status"] == "unverified"
        for case in response.json()
    )


def test_authenticated_user_can_view_case_detail():
    response = client.get(
        "/api/cases/C-TEST01",
        headers=bearer_headers(),
    )
    assert response.status_code == 200
    assert response.json()["case_id"] == "C-TEST01"


def test_decision_uses_authenticated_user_identity():
    response = client.post(
        "/api/cases/C-TEST01/decision",
        headers=bearer_headers(),
        json=decision_payload(),
    )
    assert response.status_code == 200

    session = TestingSessionLocal()
    try:
        case = session.scalar(
            select(ReviewCase).where(
                ReviewCase.case_id == "C-TEST01"
            )
        )
        assert case is not None
        assert case.review_status == "resolved"
        assert case.review_outcome == "confirmed_scam"
        assert case.reviewer == ADMIN_DISPLAY_NAME
        assert case.audit_entries
        assert case.audit_entries[-1].actor == "admin"
    finally:
        session.close()


def test_needs_more_evidence_is_final():
    first = client.post(
        "/api/cases/C-TEST01/decision",
        headers=bearer_headers(),
        json=decision_payload(
            outcome="needs_more_evidence",
            notes="Additional evidence is required.",
        ),
    )
    assert first.status_code == 200
    assert first.json()["review_status"] == "resolved"

    second = client.post(
        "/api/cases/C-TEST01/decision",
        headers=bearer_headers(),
        json=decision_payload(),
    )
    assert second.status_code == 409


# Administrator access management


def test_user_list_requires_authentication():
    assert client.get("/api/auth/users").status_code == 401


def test_admin_can_list_users_without_sensitive_fields():
    response = client.get("/api/auth/users", headers=bearer_headers())
    assert response.status_code == 200
    users = response.json()
    assert {user["username"] for user in users} == {"admin", "inactive"}
    for user in users:
        assert set(user) == {
            "id",
            "username",
            "display_name",
            "role",
            "is_active",
        }
        assert "password" not in user
        assert "password_hash" not in user


def test_reviewer_cannot_list_users():
    create_active_reviewer()
    response = client.get(
        "/api/auth/users",
        headers=bearer_headers(username="reviewer-one"),
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Administrator access is required."


def test_admin_can_create_reviewer():
    response = client.post(
        "/api/auth/users",
        headers=bearer_headers(),
        json={
            "username": "Reviewer-One",
            "password": "ReviewerPassword123!",
            "display_name": "Reviewer One",
            "role": "reviewer",
            "is_active": True,
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["username"] == "reviewer-one"
    assert body["display_name"] == "Reviewer One"
    assert body["role"] == "reviewer"
    assert body["is_active"] is True
    assert "password_hash" not in body


def test_reviewer_cannot_create_user():
    create_active_reviewer()
    response = client.post(
        "/api/auth/users",
        headers=bearer_headers(username="reviewer-one"),
        json={
            "username": "reviewer-two",
            "password": "ReviewerPassword123!",
            "display_name": "Reviewer Two",
            "role": "reviewer",
            "is_active": True,
        },
    )
    assert response.status_code == 403


def test_duplicate_username_is_rejected_case_insensitively():
    payload = {
        "username": "reviewer-one",
        "password": "ReviewerPassword123!",
        "display_name": "Reviewer One",
        "role": "reviewer",
        "is_active": True,
    }
    first = client.post(
        "/api/auth/users",
        headers=bearer_headers(),
        json=payload,
    )
    second = client.post(
        "/api/auth/users",
        headers=bearer_headers(),
        json={**payload, "username": "REVIEWER-ONE"},
    )
    assert first.status_code == 201
    assert second.status_code == 409


def test_create_user_rejects_short_password():
    response = client.post(
        "/api/auth/users",
        headers=bearer_headers(),
        json={
            "username": "reviewer-one",
            "password": "short",
            "display_name": "Reviewer One",
            "role": "reviewer",
            "is_active": True,
        },
    )
    assert response.status_code == 422


def test_created_reviewer_password_is_hashed():
    plain_password = "ReviewerPassword123!"
    response = client.post(
        "/api/auth/users",
        headers=bearer_headers(),
        json={
            "username": "reviewer-one",
            "password": plain_password,
            "display_name": "Reviewer One",
            "role": "reviewer",
            "is_active": True,
        },
    )
    assert response.status_code == 201

    session = TestingSessionLocal()
    try:
        user = session.scalar(
            select(User).where(User.username == "reviewer-one")
        )
        assert user is not None
        assert user.password_hash
        assert user.password_hash != plain_password
    finally:
        session.close()


def test_admin_can_deactivate_and_reactivate_reviewer():
    password = "ReviewerPassword123!"
    create_response = client.post(
        "/api/auth/users",
        headers=bearer_headers(),
        json={
            "username": "reviewer-one",
            "password": password,
            "display_name": "Reviewer One",
            "role": "reviewer",
            "is_active": True,
        },
    )
    user_id = create_response.json()["id"]

    deactivate = client.patch(
        "/api/auth/users/{}/status".format(user_id),
        headers=bearer_headers(),
        json={"is_active": False},
    )
    assert deactivate.status_code == 200
    assert deactivate.json()["is_active"] is False
    assert login("reviewer-one", password).status_code == 401

    reactivate = client.patch(
        "/api/auth/users/{}/status".format(user_id),
        headers=bearer_headers(),
        json={"is_active": True},
    )
    assert reactivate.status_code == 200
    assert login("reviewer-one", password).status_code == 200


def test_reviewer_cannot_change_account_status():
    reviewer = create_active_reviewer()
    response = client.patch(
        "/api/auth/users/{}/status".format(reviewer.id),
        headers=bearer_headers(username="reviewer-one"),
        json={"is_active": False},
    )
    assert response.status_code == 403


def test_admin_can_change_user_role():
    reviewer = create_active_reviewer()
    response = client.patch(
        "/api/auth/users/{}/role".format(reviewer.id),
        headers=bearer_headers(),
        json={"role": "admin"},
    )
    assert response.status_code == 200
    assert response.json()["role"] == "admin"


def test_reviewer_cannot_change_user_role():
    reviewer = create_active_reviewer()
    response = client.patch(
        "/api/auth/users/{}/role".format(reviewer.id),
        headers=bearer_headers(username="reviewer-one"),
        json={"role": "admin"},
    )
    assert response.status_code == 403


def test_unsupported_role_is_rejected():
    reviewer = create_active_reviewer()
    response = client.patch(
        "/api/auth/users/{}/role".format(reviewer.id),
        headers=bearer_headers(),
        json={"role": "superuser"},
    )
    assert response.status_code == 422


def test_admin_cannot_deactivate_own_account():
    response = client.patch(
        "/api/auth/users/1/status",
        headers=bearer_headers(),
        json={"is_active": False},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "You cannot deactivate your own account."


def test_admin_cannot_remove_own_admin_role():
    response = client.patch(
        "/api/auth/users/1/role",
        headers=bearer_headers(),
        json={"role": "reviewer"},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == (
        "You cannot remove your own administrator role."
    )


def test_missing_user_updates_return_404():
    status_response = client.patch(
        "/api/auth/users/9999/status",
        headers=bearer_headers(),
        json={"is_active": False},
    )
    role_response = client.patch(
        "/api/auth/users/9999/role",
        headers=bearer_headers(),
        json={"role": "reviewer"},
    )
    assert status_response.status_code == 404
    assert role_response.status_code == 404


# Public endpoints


def test_health_endpoint_remains_public():
    assert client.get("/api/health").status_code == 200


def test_analysis_formats_endpoint_remains_public():
    response = client.get("/api/analyse/formats")
    assert response.status_code != 401


# Registry management


def test_registry_list_requires_authentication():
    response = client.get("/api/registry")
    assert response.status_code == 401


def test_reviewer_cannot_list_registry_records():
    create_active_reviewer()

    response = client.get(
        "/api/registry",
        headers=bearer_headers(
            username="reviewer-one",
        ),
    )

    assert response.status_code == 403
    assert (
        response.json()["detail"]
        == "Administrator access is required."
    )


def test_admin_can_list_registry_records():
    response = client.get(
        "/api/registry",
        headers=bearer_headers(),
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)


# Registry management


def test_registry_list_requires_authentication():
    response = client.get("/api/registry")
    assert response.status_code == 401


def test_reviewer_cannot_list_registry_records():
    create_active_reviewer()

    response = client.get(
        "/api/registry",
        headers=bearer_headers(
            username="reviewer-one",
        ),
    )

    assert response.status_code == 403
    assert (
        response.json()["detail"]
        == "Administrator access is required."
    )


def test_admin_can_list_registry_records():
    response = client.get(
        "/api/registry",
        headers=bearer_headers(),
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def company_registry_payload():
    return {
        "category": "company",
        "external_id": "C-TEST-REGISTRY",
        "name": "Test Registry Company Limited",
        "registration_number": "C.TEST.2026",
        "status": "active",
        "county": "Nairobi",
        "record_is_mock": True,
    }


def test_registry_create_requires_authentication():
    response = client.post(
        "/api/registry",
        json=company_registry_payload(),
    )

    assert response.status_code == 401


def test_reviewer_cannot_create_registry_record():
    create_active_reviewer()

    response = client.post(
        "/api/registry",
        headers=bearer_headers(
            username="reviewer-one",
        ),
        json=company_registry_payload(),
    )

    assert response.status_code == 403
    assert (
        response.json()["detail"]
        == "Administrator access is required."
    )


def test_admin_can_create_company_registry_record():
    response = client.post(
        "/api/registry",
        headers=bearer_headers(),
        json=company_registry_payload(),
    )

    assert response.status_code == 201

    body = response.json()

    assert body["category"] == "company"
    assert body["external_id"] == "C-TEST-REGISTRY"
    assert body["name"] == "Test Registry Company Limited"
    assert body["registration_number"] == "C.TEST.2026"
    assert body["is_active"] is True
    assert body["created_by"] == "admin"

    session = TestingSessionLocal()

    try:
        record = session.scalar(
            select(RegistryRecord).where(
                RegistryRecord.external_id
                == "C-TEST-REGISTRY"
            )
        )

        assert record is not None

        audit = session.scalar(
            select(RegistryAuditEntry).where(
                RegistryAuditEntry.registry_record_id
                == record.id
            )
        )

        assert audit is not None
        assert audit.actor == "admin"
        assert audit.action == "created"
    finally:
        session.close()


def test_duplicate_active_registry_name_is_rejected():
    first = client.post(
        "/api/registry",
        headers=bearer_headers(),
        json=company_registry_payload(),
    )

    assert first.status_code == 201

    duplicate = company_registry_payload()
    duplicate["external_id"] = "C-TEST-DUPLICATE"
    duplicate["registration_number"] = "C.TEST.DUPLICATE"

    second = client.post(
        "/api/registry",
        headers=bearer_headers(),
        json=duplicate,
    )

    assert second.status_code == 409


def _create_test_company():
    response = client.post(
        "/api/registry",
        headers=bearer_headers(),
        json=company_registry_payload(),
    )

    assert response.status_code == 201

    return response.json()


def test_registry_update_requires_authentication():
    response = client.patch(
        "/api/registry/999",
        json={"county": "Kiambu"},
    )

    assert response.status_code == 401


def test_reviewer_cannot_update_registry_record():
    created = _create_test_company()
    create_active_reviewer()

    response = client.patch(
        "/api/registry/{}".format(created["id"]),
        headers=bearer_headers(
            username="reviewer-one",
        ),
        json={"county": "Kiambu"},
    )

    assert response.status_code == 403
    assert (
        response.json()["detail"]
        == "Administrator access is required."
    )


def test_admin_can_update_registry_record():
    created = _create_test_company()

    response = client.patch(
        "/api/registry/{}".format(created["id"]),
        headers=bearer_headers(),
        json={
            "name": "Updated Registry Company Limited",
            "county": "Kiambu",
            "status": "dormant",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["name"] == "Updated Registry Company Limited"
    assert body["county"] == "Kiambu"
    assert body["status"] == "dormant"
    assert body["updated_by"] == "admin"

    session = TestingSessionLocal()

    try:
        audits = session.scalars(
            select(RegistryAuditEntry)
            .where(
                RegistryAuditEntry.registry_record_id
                == created["id"]
            )
            .order_by(
                RegistryAuditEntry.id.asc()
            )
        ).all()

        assert [entry.action for entry in audits] == [
            "created",
            "updated",
        ]

        assert audits[-1].actor == "admin"
        assert "county" in audits[-1].details_json
        assert "status" in audits[-1].details_json
    finally:
        session.close()


def test_registry_update_rejects_missing_record():
    response = client.patch(
        "/api/registry/999999",
        headers=bearer_headers(),
        json={"county": "Kiambu"},
    )

    assert response.status_code == 404


def test_registry_update_rejects_empty_request():
    created = _create_test_company()

    response = client.patch(
        "/api/registry/{}".format(created["id"]),
        headers=bearer_headers(),
        json={},
    )

    assert response.status_code == 422


def test_registry_update_rejects_unchanged_values():
    created = _create_test_company()

    response = client.patch(
        "/api/registry/{}".format(created["id"]),
        headers=bearer_headers(),
        json={"county": "Nairobi"},
    )

    assert response.status_code == 409


def test_registry_status_update_requires_authentication():
    response = client.patch(
        "/api/registry/999/status",
        json={"is_active": False},
    )

    assert response.status_code == 401


def test_reviewer_cannot_change_registry_status():
    created = _create_test_company()
    create_active_reviewer()

    response = client.patch(
        "/api/registry/{}/status".format(
            created["id"]
        ),
        headers=bearer_headers(
            username="reviewer-one",
        ),
        json={"is_active": False},
    )

    assert response.status_code == 403
    assert (
        response.json()["detail"]
        == "Administrator access is required."
    )


def test_admin_can_deactivate_registry_record():
    created = _create_test_company()

    response = client.patch(
        "/api/registry/{}/status".format(
            created["id"]
        ),
        headers=bearer_headers(),
        json={"is_active": False},
    )

    assert response.status_code == 200

    body = response.json()

    assert body["is_active"] is False
    assert body["updated_by"] == "admin"

    session = TestingSessionLocal()

    try:
        audits = session.scalars(
            select(RegistryAuditEntry)
            .where(
                RegistryAuditEntry.registry_record_id
                == created["id"]
            )
            .order_by(
                RegistryAuditEntry.id.asc()
            )
        ).all()

        assert [entry.action for entry in audits] == [
            "created",
            "deactivated",
        ]

        assert audits[-1].actor == "admin"
        assert '"after": false' in audits[-1].details_json
    finally:
        session.close()


def test_admin_can_reactivate_registry_record():
    created = _create_test_company()

    deactivated = client.patch(
        "/api/registry/{}/status".format(
            created["id"]
        ),
        headers=bearer_headers(),
        json={"is_active": False},
    )

    assert deactivated.status_code == 200

    reactivated = client.patch(
        "/api/registry/{}/status".format(
            created["id"]
        ),
        headers=bearer_headers(),
        json={"is_active": True},
    )

    assert reactivated.status_code == 200
    assert reactivated.json()["is_active"] is True

    session = TestingSessionLocal()

    try:
        audits = session.scalars(
            select(RegistryAuditEntry)
            .where(
                RegistryAuditEntry.registry_record_id
                == created["id"]
            )
            .order_by(
                RegistryAuditEntry.id.asc()
            )
        ).all()

        assert [entry.action for entry in audits] == [
            "created",
            "deactivated",
            "activated",
        ]
    finally:
        session.close()


def test_registry_status_rejects_unchanged_state():
    created = _create_test_company()

    response = client.patch(
        "/api/registry/{}/status".format(
            created["id"]
        ),
        headers=bearer_headers(),
        json={"is_active": True},
    )

    assert response.status_code == 409
    assert (
        response.json()["detail"]
        == "The registry record is already active."
    )


def test_registry_status_rejects_missing_record():
    response = client.patch(
        "/api/registry/999999/status",
        headers=bearer_headers(),
        json={"is_active": False},
    )

    assert response.status_code == 404


def test_registry_audit_requires_authentication():
    response = client.get(
        "/api/registry/999/audit"
    )

    assert response.status_code == 401


def test_reviewer_cannot_view_registry_audit_history():
    created = _create_test_company()
    create_active_reviewer()

    response = client.get(
        "/api/registry/{}/audit".format(
            created["id"]
        ),
        headers=bearer_headers(
            username="reviewer-one",
        ),
    )

    assert response.status_code == 403
    assert (
        response.json()["detail"]
        == "Administrator access is required."
    )


def test_admin_can_view_registry_audit_history():
    created = _create_test_company()

    updated = client.patch(
        "/api/registry/{}".format(
            created["id"]
        ),
        headers=bearer_headers(),
        json={
            "county": "Kiambu",
        },
    )

    assert updated.status_code == 200

    deactivated = client.patch(
        "/api/registry/{}/status".format(
            created["id"]
        ),
        headers=bearer_headers(),
        json={
            "is_active": False,
        },
    )

    assert deactivated.status_code == 200

    response = client.get(
        "/api/registry/{}/audit".format(
            created["id"]
        ),
        headers=bearer_headers(),
    )

    assert response.status_code == 200

    entries = response.json()

    assert [
        entry["action"]
        for entry in entries
    ] == [
        "deactivated",
        "updated",
        "created",
    ]

    assert all(
        entry["actor"] == "admin"
        for entry in entries
    )

    assert all(
        entry["registry_record_id"]
        == created["id"]
        for entry in entries
    )


def test_registry_audit_rejects_missing_record():
    response = client.get(
        "/api/registry/999999/audit",
        headers=bearer_headers(),
    )

    assert response.status_code == 404
