"""Unit tests for the SafeHire government dashboard API client."""

from unittest.mock import Mock

import pytest
import requests

from app.government.api_client import SafeHireAPIClient, SafeHireAPIError


def make_response(status_code=200, json_data=None):
    """Create a small mock that behaves like requests.Response."""
    response = Mock()
    response.status_code = status_code
    response.ok = 200 <= status_code < 300
    response.json.return_value = json_data
    return response


def patch_request(monkeypatch, response=None, side_effect=None):
    """Patch requests.Session.request and return the request mock."""
    request_mock = Mock(return_value=response, side_effect=side_effect)
    monkeypatch.setattr(requests.Session, "request", request_mock)
    return request_mock


def test_health_returns_api_information(monkeypatch):
    response = make_response(
        json_data={
            "status": "ok",
            "version": "0.1.0",
            "model": "stub",
        }
    )
    request_mock = patch_request(monkeypatch, response=response)

    client = SafeHireAPIClient()
    result = client.health()

    assert result["status"] == "ok"
    assert result["version"] == "0.1.0"
    assert result["model"] == "stub"
    assert request_mock.call_args.kwargs["method"] == "GET"
    assert request_mock.call_args.kwargs["url"].endswith("/api/health")


def test_custom_base_url_is_used(monkeypatch):
    response = make_response(json_data={"status": "ok"})
    request_mock = patch_request(monkeypatch, response=response)

    client = SafeHireAPIClient(base_url="https://example.test/")
    client.health()

    assert request_mock.call_args.kwargs["url"] == (
        "https://example.test/api/health"
    )


def test_environment_base_url_is_used(monkeypatch):
    monkeypatch.setenv("SAFEHIRE_API_BASE_URL", "https://environment.example")
    response = make_response(json_data={"status": "ok"})
    request_mock = patch_request(monkeypatch, response=response)

    client = SafeHireAPIClient()
    client.health()

    assert request_mock.call_args.kwargs["url"] == (
        "https://environment.example/api/health"
    )


def test_login_sends_credentials_and_retains_token(monkeypatch):
    login_result = {
        "access_token": "signed-test-token",
        "token_type": "bearer",
        "reviewer": {
            "id": 1,
            "username": "admin",
            "display_name": "SafeHire Administrator",
            "role": "admin",
            "is_active": True,
        },
    }
    response = make_response(json_data=login_result)
    request_mock = patch_request(monkeypatch, response=response)

    client = SafeHireAPIClient()
    result = client.login(" admin ", "StrongPassword123!")

    assert result == login_result
    assert client.access_token == "signed-test-token"
    request = request_mock.call_args.kwargs
    assert request["method"] == "POST"
    assert request["url"].endswith("/api/auth/login")
    assert request["json"] == {
        "username": "admin",
        "password": "StrongPassword123!",
    }


@pytest.mark.parametrize("username", ["", "   "])
def test_login_requires_username(username):
    client = SafeHireAPIClient()

    with pytest.raises(ValueError, match="Username is required"):
        client.login(username, "StrongPassword123!")


def test_login_requires_password():
    client = SafeHireAPIClient()

    with pytest.raises(ValueError, match="Password is required"):
        client.login("admin", "")


def test_login_requires_access_token_in_response(monkeypatch):
    response = make_response(json_data={"reviewer": {"username": "admin"}})
    patch_request(monkeypatch, response=response)

    client = SafeHireAPIClient()

    with pytest.raises(SafeHireAPIError, match="access token"):
        client.login("admin", "StrongPassword123!")


def test_login_requires_reviewer_profile_in_response(monkeypatch):
    response = make_response(json_data={"access_token": "token"})
    patch_request(monkeypatch, response=response)

    client = SafeHireAPIClient()

    with pytest.raises(SafeHireAPIError, match="reviewer profile"):
        client.login("admin", "StrongPassword123!")


def test_get_current_user_sends_bearer_token(monkeypatch):
    profile = {
        "id": 1,
        "username": "admin",
        "display_name": "SafeHire Administrator",
        "role": "admin",
        "is_active": True,
    }
    response = make_response(json_data=profile)
    request_mock = patch_request(monkeypatch, response=response)

    client = SafeHireAPIClient(access_token="test-token")
    result = client.get_current_user()

    assert result == profile
    assert request_mock.call_args.kwargs["headers"]["Authorization"] == (
        "Bearer test-token"
    )


def test_logout_clears_access_token():
    client = SafeHireAPIClient(access_token="temporary-token")

    client.logout()

    assert client.access_token is None


def test_get_cases_accepts_empty_queue(monkeypatch):
    response = make_response(json_data=[])
    patch_request(monkeypatch, response=response)

    assert SafeHireAPIClient().get_cases() == []


def test_get_cases_returns_cases(monkeypatch):
    cases = [
        {
            "case_id": "C-TEST01",
            "risk_level": "high_risk",
            "verification_status": "unverified",
            "review_status": "open",
        }
    ]
    response = make_response(json_data=cases)
    patch_request(monkeypatch, response=response)

    assert SafeHireAPIClient().get_cases() == cases


def test_get_cases_sends_all_filters(monkeypatch):
    response = make_response(json_data=[])
    request_mock = patch_request(monkeypatch, response=response)

    client = SafeHireAPIClient(access_token="test-token")
    client.get_cases(
        risk_level="high_risk",
        review_status="open",
        is_overseas=True,
        limit=25,
    )

    request = request_mock.call_args.kwargs
    assert request["params"] == {
        "risk_level": "high_risk",
        "review_status": "open",
        "is_overseas": True,
        "limit": 25,
    }
    assert request["headers"]["Authorization"] == "Bearer test-token"


def test_get_cases_omits_empty_optional_filters(monkeypatch):
    response = make_response(json_data=[])
    request_mock = patch_request(monkeypatch, response=response)

    SafeHireAPIClient().get_cases(limit=50)

    assert request_mock.call_args.kwargs["params"] == {"limit": 50}


@pytest.mark.parametrize("invalid_limit", [0, -1, 201, 500])
def test_get_cases_rejects_invalid_limit(invalid_limit):
    client = SafeHireAPIClient()

    with pytest.raises(ValueError, match="between 1 and 200"):
        client.get_cases(limit=invalid_limit)


def test_get_cases_rejects_non_list_response(monkeypatch):
    response = make_response(json_data={"items": []})
    patch_request(monkeypatch, response=response)

    with pytest.raises(SafeHireAPIError, match="not a JSON list"):
        SafeHireAPIClient().get_cases()


def test_get_stats_returns_statistics(monkeypatch):
    statistics = {"total": 2, "open": 1, "resolved": 1, "high_risk": 1}
    response = make_response(json_data=statistics)
    patch_request(monkeypatch, response=response)

    assert SafeHireAPIClient().get_stats() == statistics


def test_get_stats_rejects_non_object_response(monkeypatch):
    response = make_response(json_data=[])
    patch_request(monkeypatch, response=response)

    with pytest.raises(SafeHireAPIError, match="not a JSON object"):
        SafeHireAPIClient().get_stats()


def test_get_case_returns_case_detail(monkeypatch):
    case = {
        "case_id": "C-TEST01",
        "risk_level": "suspicious",
        "verification_status": "unverified",
        "review_status": "open",
        "audit_trail": [],
    }
    response = make_response(json_data=case)
    patch_request(monkeypatch, response=response)

    assert SafeHireAPIClient().get_case("C-TEST01") == case


@pytest.mark.parametrize("case_id", ["", "   ", None])
def test_get_case_requires_case_id(case_id):
    client = SafeHireAPIClient()

    with pytest.raises(ValueError, match="case_id is required"):
        client.get_case(case_id)


def test_submit_decision_sends_authenticated_payload(monkeypatch):
    updated_case = {
        "case_id": "C-TEST01",
        "review_status": "resolved",
        "review_outcome": "confirmed_scam",
        "reviewer": "SafeHire Administrator",
    }
    response = make_response(json_data=updated_case)
    request_mock = patch_request(monkeypatch, response=response)

    client = SafeHireAPIClient(access_token="test-token")
    result = client.submit_decision(
        case_id="C-TEST01",
        outcome="confirmed_scam",
        notes="Evidence reviewed.",
        reviewer="SafeHire Administrator",
    )

    assert result == updated_case
    request = request_mock.call_args.kwargs
    assert request["headers"]["Authorization"] == "Bearer test-token"
    assert request["json"] == {
        "outcome": "confirmed_scam",
        "notes": "Evidence reviewed.",
        "reviewer": "SafeHire Administrator",
    }


@pytest.mark.parametrize("reviewer", ["", "   ", None])
def test_submit_decision_allows_missing_reviewer(monkeypatch, reviewer):
    updated_case = {
        "case_id": "C-TEST01",
        "review_status": "resolved",
        "review_outcome": "confirmed_scam",
        "reviewer": "SafeHire Administrator",
    }
    response = make_response(json_data=updated_case)
    request_mock = patch_request(monkeypatch, response=response)

    client = SafeHireAPIClient(access_token="test-token")
    result = client.submit_decision(
        case_id="C-TEST01",
        outcome="confirmed_scam",
        notes="Test",
        reviewer=reviewer,
    )

    assert result == updated_case
    request = request_mock.call_args.kwargs
    assert request["headers"]["Authorization"] == "Bearer test-token"
    assert request["json"] == {
        "outcome": "confirmed_scam",
        "notes": "Test",
    }


@pytest.mark.parametrize("case_id", ["", "   ", None])
def test_submit_decision_requires_case_id(case_id):
    client = SafeHireAPIClient()

    with pytest.raises(ValueError, match="case_id is required"):
        client.submit_decision(
            case_id=case_id,
            outcome="confirmed_scam",
            notes="Test",
        )


@pytest.mark.parametrize("outcome", ["", "   ", None])
def test_submit_decision_requires_outcome(outcome):
    client = SafeHireAPIClient()

    with pytest.raises(ValueError, match="outcome is required"):
        client.submit_decision(
            case_id="C-TEST01",
            outcome=outcome,
            notes="Test",
        )


def test_login_401_uses_credentials_message(monkeypatch):
    response = make_response(
        status_code=401,
        json_data={"detail": "Invalid username or password."},
    )
    patch_request(monkeypatch, response=response)

    with pytest.raises(SafeHireAPIError) as error:
        SafeHireAPIClient().login("admin", "wrong-password")

    assert error.value.status_code == 401
    assert error.value.message == "Invalid username or password."


def test_profile_401_uses_session_message(monkeypatch):
    response = make_response(status_code=401, json_data={})
    patch_request(monkeypatch, response=response)

    with pytest.raises(SafeHireAPIError) as error:
        SafeHireAPIClient().get_current_user()

    assert error.value.status_code == 401
    assert "session" in error.value.message.lower()


def test_timeout_becomes_dashboard_error(monkeypatch):
    patch_request(monkeypatch, side_effect=requests.Timeout())

    with pytest.raises(SafeHireAPIError, match="too long"):
        SafeHireAPIClient().health()


def test_connection_error_becomes_dashboard_error(monkeypatch):
    patch_request(monkeypatch, side_effect=requests.ConnectionError())

    with pytest.raises(SafeHireAPIError, match="could not be reached"):
        SafeHireAPIClient().health()


def test_validation_error_preserves_status_and_details(monkeypatch):
    details = {"detail": [{"msg": "Invalid outcome"}]}
    response = make_response(status_code=422, json_data=details)
    patch_request(monkeypatch, response=response)

    with pytest.raises(SafeHireAPIError) as error:
        SafeHireAPIClient().submit_decision(
            case_id="C-TEST01",
            outcome="unsupported",
            notes="Test",
        )

    assert error.value.status_code == 422
    assert error.value.details == details


def test_server_error_becomes_dashboard_error(monkeypatch):
    response = make_response(
        status_code=500,
        json_data={"detail": "Internal server error"},
    )
    patch_request(monkeypatch, response=response)

    with pytest.raises(SafeHireAPIError) as error:
        SafeHireAPIClient().health()

    assert error.value.status_code == 500
    assert "internal error" in error.value.message.lower()


def test_invalid_json_becomes_dashboard_error(monkeypatch):
    response = Mock()
    response.status_code = 200
    response.ok = True
    response.json.side_effect = ValueError("Invalid JSON")
    patch_request(monkeypatch, response=response)

    with pytest.raises(SafeHireAPIError, match="invalid JSON response"):
        SafeHireAPIClient().health()
