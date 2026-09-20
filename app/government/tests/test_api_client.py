from unittest.mock import Mock

import pytest
import requests

from app.government.api_client import (
    HakikiHireAPIClient,
    HakikiHireAPIError,
)


def make_response(status_code=200, json_data=None):
    """Return a small mock that behaves like requests.Response."""
    response = Mock()
    response.status_code = status_code
    response.ok = 200 <= status_code < 300
    response.json.return_value = json_data
    return response


def patch_request(monkeypatch, response=None, side_effect=None):
    """Patch requests.Session.request and return the request mock."""
    request_mock = Mock(
        return_value=response,
        side_effect=side_effect,
    )
    monkeypatch.setattr(
        requests.Session,
        "request",
        request_mock,
    )
    return request_mock


def test_health_returns_api_information(monkeypatch):
    response = make_response(
        json_data={
            "status": "ok",
            "version": "0.1.0",
            "model": "stub",
            "thresholds": {
                "high_risk": 0.7,
                "suspicious": 0.35,
            },
        }
    )
    request_mock = patch_request(monkeypatch, response=response)

    client = HakikiHireAPIClient()
    result = client.health()

    assert result["status"] == "ok"
    assert result["version"] == "0.1.0"
    assert result["model"] == "stub"
    assert result["thresholds"]["high_risk"] == 0.7

    request_mock.assert_called_once()
    request = request_mock.call_args.kwargs
    assert request["method"] == "GET"
    assert request["url"] == "http://127.0.0.1:8000/api/health"


def test_custom_base_url_is_used(monkeypatch):
    response = make_response(json_data={"status": "ok"})
    request_mock = patch_request(monkeypatch, response=response)

    client = HakikiHireAPIClient(base_url="https://example.test/")
    client.health()

    request = request_mock.call_args.kwargs
    assert request["url"] == "https://example.test/api/health"


def test_environment_base_url_is_used(monkeypatch):
    monkeypatch.setenv(
        "HAKIKI_HIRE_API_BASE_URL",
        "https://environment.example",
    )
    response = make_response(json_data={"status": "ok"})
    request_mock = patch_request(monkeypatch, response=response)

    client = HakikiHireAPIClient()
    client.health()

    request = request_mock.call_args.kwargs
    assert request["url"] == "https://environment.example/api/health"


def test_get_cases_accepts_empty_queue(monkeypatch):
    response = make_response(json_data=[])
    patch_request(monkeypatch, response=response)

    client = HakikiHireAPIClient()

    assert client.get_cases() == []


def test_get_cases_returns_cases(monkeypatch):
    cases = [
        {
            "case_id": "C-TEST01",
            "entity_name": None,
            "title": None,
            "risk_level": "high_risk",
            "verification_status": "unverified",
            "is_overseas": True,
            "created_at": "2026-09-12T06:45:54.953338",
            "review_status": "open",
        }
    ]
    response = make_response(json_data=cases)
    patch_request(monkeypatch, response=response)

    client = HakikiHireAPIClient()

    assert client.get_cases() == cases


def test_get_cases_sends_all_filters(monkeypatch):
    response = make_response(json_data=[])
    request_mock = patch_request(monkeypatch, response=response)

    client = HakikiHireAPIClient()
    client.get_cases(
        risk_level="high_risk",
        review_status="open",
        is_overseas=True,
        limit=25,
    )

    request = request_mock.call_args.kwargs
    assert request["method"] == "GET"
    assert request["url"] == "http://127.0.0.1:8000/api/cases"
    assert request["params"] == {
        "risk_level": "high_risk",
        "review_status": "open",
        "is_overseas": True,
        "limit": 25,
    }


def test_get_cases_omits_empty_optional_filters(monkeypatch):
    response = make_response(json_data=[])
    request_mock = patch_request(monkeypatch, response=response)

    client = HakikiHireAPIClient()
    client.get_cases(limit=50)

    request = request_mock.call_args.kwargs
    assert request["params"] == {"limit": 50}


@pytest.mark.parametrize("invalid_limit", [0, -1, 201, 500])
def test_get_cases_rejects_invalid_limit(invalid_limit):
    client = HakikiHireAPIClient()

    with pytest.raises(ValueError, match="between 1 and 200"):
        client.get_cases(limit=invalid_limit)


def test_get_cases_rejects_non_list_response(monkeypatch):
    response = make_response(json_data={"items": []})
    patch_request(monkeypatch, response=response)

    client = HakikiHireAPIClient()

    with pytest.raises(HakikiHireAPIError, match="not a JSON list"):
        client.get_cases()


def test_get_stats_returns_statistics(monkeypatch):
    statistics = {
        "total": 2,
        "open": 1,
        "resolved": 1,
        "high_risk": 1,
    }
    response = make_response(json_data=statistics)
    request_mock = patch_request(monkeypatch, response=response)

    client = HakikiHireAPIClient()
    result = client.get_stats()

    assert result == statistics
    request = request_mock.call_args.kwargs
    assert request["url"] == "http://127.0.0.1:8000/api/cases/stats"


def test_get_stats_rejects_non_object_response(monkeypatch):
    response = make_response(json_data=[])
    patch_request(monkeypatch, response=response)

    client = HakikiHireAPIClient()

    with pytest.raises(HakikiHireAPIError, match="not a JSON object"):
        client.get_stats()


def test_get_case_returns_case_detail(monkeypatch):
    case = {
        "case_id": "C-TEST01",
        "risk_level": "suspicious",
        "verification_status": "unverified",
        "review_status": "open",
        "probability": 0.61,
        "reasons": [],
        "audit_trail": [],
    }
    response = make_response(json_data=case)
    request_mock = patch_request(monkeypatch, response=response)

    client = HakikiHireAPIClient()
    result = client.get_case("C-TEST01")

    assert result == case
    request = request_mock.call_args.kwargs
    assert request["method"] == "GET"
    assert request["url"] == "http://127.0.0.1:8000/api/cases/C-TEST01"


@pytest.mark.parametrize("case_id", ["", "   ", None])
def test_get_case_requires_case_id(case_id):
    client = HakikiHireAPIClient()

    with pytest.raises(ValueError, match="case_id is required"):
        client.get_case(case_id)


def test_submit_decision_sends_correct_payload(monkeypatch):
    updated_case = {
        "case_id": "C-TEST01",
        "review_status": "resolved",
        "review_outcome": "confirmed_scam",
        "review_notes": "Evidence reviewed.",
    }
    response = make_response(json_data=updated_case)
    request_mock = patch_request(monkeypatch, response=response)

    client = HakikiHireAPIClient()
    result = client.submit_decision(
        case_id="C-TEST01",
        outcome="confirmed_scam",
        notes="Evidence reviewed.",
        reviewer="Test Reviewer",
    )

    assert result == updated_case
    request = request_mock.call_args.kwargs
    assert request["method"] == "POST"
    assert request["url"] == (
        "http://127.0.0.1:8000/api/cases/C-TEST01/decision"
    )
    assert request["json"] == {
        "outcome": "confirmed_scam",
        "notes": "Evidence reviewed.",
        "reviewer": "Test Reviewer",
    }


def test_submit_decision_strips_text_values(monkeypatch):
    response = make_response(
        json_data={
            "case_id": "C-TEST01",
            "review_status": "resolved",
        }
    )
    request_mock = patch_request(monkeypatch, response=response)

    client = HakikiHireAPIClient()
    client.submit_decision(
        case_id="  C-TEST01  ",
        outcome="  confirmed_legitimate  ",
        notes="  Registry details reviewed.  ",
        reviewer="  Test Reviewer  ",
    )

    request = request_mock.call_args.kwargs
    assert request["url"].endswith("/api/cases/C-TEST01/decision")
    assert request["json"] == {
        "outcome": "confirmed_legitimate",
        "notes": "Registry details reviewed.",
        "reviewer": "Test Reviewer",
    }


@pytest.mark.parametrize("case_id", ["", "   ", None])
def test_submit_decision_requires_case_id(case_id):
    client = HakikiHireAPIClient()

    with pytest.raises(ValueError, match="case_id is required"):
        client.submit_decision(
            case_id=case_id,
            outcome="confirmed_scam",
            notes="Test",
            reviewer="Test Reviewer",
        )


@pytest.mark.parametrize("outcome", ["", "   ", None])
def test_submit_decision_requires_outcome(outcome):
    client = HakikiHireAPIClient()

    with pytest.raises(ValueError, match="outcome is required"):
        client.submit_decision(
            case_id="C-TEST01",
            outcome=outcome,
            notes="Test",
            reviewer="Test Reviewer",
        )


@pytest.mark.parametrize("reviewer", ["", "   ", None])
def test_submit_decision_requires_reviewer(reviewer):
    client = HakikiHireAPIClient()

    with pytest.raises(ValueError, match="reviewer is required"):
        client.submit_decision(
            case_id="C-TEST01",
            outcome="confirmed_scam",
            notes="Test",
            reviewer=reviewer,
        )


def test_timeout_becomes_dashboard_error(monkeypatch):
    patch_request(monkeypatch, side_effect=requests.Timeout())
    client = HakikiHireAPIClient()

    with pytest.raises(HakikiHireAPIError, match="too long"):
        client.health()


def test_connection_error_becomes_dashboard_error(monkeypatch):
    patch_request(monkeypatch, side_effect=requests.ConnectionError())
    client = HakikiHireAPIClient()

    with pytest.raises(HakikiHireAPIError, match="could not be reached"):
        client.health()


def test_not_found_error_preserves_status_and_details(monkeypatch):
    details = {"detail": "Case not found"}
    response = make_response(status_code=404, json_data=details)
    patch_request(monkeypatch, response=response)

    client = HakikiHireAPIClient()

    with pytest.raises(HakikiHireAPIError) as error:
        client.get_case("C-MISSING")

    assert error.value.status_code == 404
    assert error.value.details == details


def test_conflict_error_preserves_status_and_details(monkeypatch):
    details = {"detail": "Decision already recorded"}
    response = make_response(status_code=409, json_data=details)
    patch_request(monkeypatch, response=response)

    client = HakikiHireAPIClient()

    with pytest.raises(HakikiHireAPIError) as error:
        client.submit_decision(
            case_id="C-TEST01",
            outcome="confirmed_scam",
            notes="Test",
            reviewer="Test Reviewer",
        )

    assert error.value.status_code == 409
    assert error.value.details == details


def test_validation_error_preserves_status_and_details(monkeypatch):
    details = {
        "detail": [
            {
                "loc": ["body", "outcome"],
                "msg": "Invalid outcome",
                "type": "enum",
            }
        ]
    }
    response = make_response(status_code=422, json_data=details)
    patch_request(monkeypatch, response=response)

    client = HakikiHireAPIClient()

    with pytest.raises(HakikiHireAPIError) as error:
        client.submit_decision(
            case_id="C-TEST01",
            outcome="unsupported",
            notes="Test",
            reviewer="Test Reviewer",
        )

    assert error.value.status_code == 422
    assert error.value.details == details


def test_server_error_becomes_dashboard_error(monkeypatch):
    response = make_response(
        status_code=500,
        json_data={"detail": "Internal server error"},
    )
    patch_request(monkeypatch, response=response)

    client = HakikiHireAPIClient()

    with pytest.raises(HakikiHireAPIError) as error:
        client.health()

    assert error.value.status_code == 500
    assert "internal error" in error.value.message.lower()


def test_invalid_json_becomes_dashboard_error(monkeypatch):
    response = Mock()
    response.status_code = 200
    response.ok = True
    response.json.side_effect = ValueError("Invalid JSON")
    patch_request(monkeypatch, response=response)

    client = HakikiHireAPIClient()

    with pytest.raises(HakikiHireAPIError, match="invalid JSON response"):
        client.health()
# Registry Management API client
# Registry Management API client


def test_registry_client_lists_records(monkeypatch):
    client = HakikiHireAPIClient(
        base_url="https://example.test",
        access_token="test-token",
    )
    captured = {}

    def fake_request(method, path, params=None, json_body=None):
        captured.update(
            {
                "method": method,
                "path": path,
                "params": params,
                "json_body": json_body,
            }
        )
        return [{"id": 1, "category": "company", "name": "Example Company"}]

    monkeypatch.setattr(client, "_request", fake_request)

    result = client.get_registry_records(
        category="company",
        search="Example",
        include_inactive=True,
    )

    assert result[0]["name"] == "Example Company"
    assert captured == {
        "method": "GET",
        "path": "/api/registry",
        "params": {
            "include_inactive": True,
            "category": "company",
            "search": "Example",
        },
        "json_body": None,
    }


def test_registry_client_rejects_invalid_category():
    client = HakikiHireAPIClient(
        base_url="https://example.test",
    )

    with pytest.raises(ValueError, match="category must be company"):
        client.get_registry_records(category="unknown")


def test_registry_client_creates_record(monkeypatch):
    client = HakikiHireAPIClient(
        base_url="https://example.test",
        access_token="test-token",
    )
    captured = {}

    def fake_request(method, path, params=None, json_body=None):
        captured.update(
            {
                "method": method,
                "path": path,
                "json_body": json_body,
            }
        )
        return {
            "id": 7,
            "category": "company",
            "name": "Example Company",
        }

    monkeypatch.setattr(client, "_request", fake_request)

    result = client.create_registry_record(
        {
            "category": "company",
            "name": "  Example Company  ",
            "external_id": "C-007",
            "registration_number": "C.007",
        }
    )

    assert result["id"] == 7
    assert captured["method"] == "POST"
    assert captured["path"] == "/api/registry"
    assert captured["json_body"]["name"] == "Example Company"


def test_registry_client_updates_record(monkeypatch):
    client = HakikiHireAPIClient(
        base_url="https://example.test",
        access_token="test-token",
    )
    captured = {}

    def fake_request(method, path, params=None, json_body=None):
        captured.update(
            {
                "method": method,
                "path": path,
                "json_body": json_body,
            }
        )
        return {"id": 7, "county": "Kiambu"}

    monkeypatch.setattr(client, "_request", fake_request)

    result = client.update_registry_record(
        7,
        {"county": "Kiambu"},
    )

    assert result["county"] == "Kiambu"
    assert captured == {
        "method": "PATCH",
        "path": "/api/registry/7",
        "json_body": {"county": "Kiambu"},
    }


def test_registry_client_changes_status(monkeypatch):
    client = HakikiHireAPIClient(
        base_url="https://example.test",
        access_token="test-token",
    )
    captured = {}

    def fake_request(method, path, params=None, json_body=None):
        captured.update(
            {
                "method": method,
                "path": path,
                "json_body": json_body,
            }
        )
        return {"id": 7, "is_active": False}

    monkeypatch.setattr(client, "_request", fake_request)

    result = client.update_registry_record_status(
        7,
        False,
    )

    assert result["is_active"] is False
    assert captured == {
        "method": "PATCH",
        "path": "/api/registry/7/status",
        "json_body": {"is_active": False},
    }


def test_registry_client_gets_audit_history(monkeypatch):
    client = HakikiHireAPIClient(
        base_url="https://example.test",
        access_token="test-token",
    )
    captured = {}

    def fake_request(method, path, params=None, json_body=None):
        captured.update(
            {
                "method": method,
                "path": path,
            }
        )
        return [{"id": 1, "action": "created"}]

    monkeypatch.setattr(client, "_request", fake_request)

    result = client.get_registry_audit_history(7)

    assert result[0]["action"] == "created"
    assert captured == {
        "method": "GET",
        "path": "/api/registry/7/audit",
    }


def test_registry_client_validates_record_ids():
    client = HakikiHireAPIClient(
        base_url="https://example.test",
    )

    with pytest.raises(ValueError, match="valid registry record ID"):
        client.update_registry_record(0, {"county": "Kiambu"})

    with pytest.raises(ValueError, match="valid registry record ID"):
        client.update_registry_record_status(0, False)

    with pytest.raises(ValueError, match="valid registry record ID"):
        client.get_registry_audit_history(0)


def test_registry_client_rejects_invalid_response_types(monkeypatch):
    client = HakikiHireAPIClient(
        base_url="https://example.test",
    )

    monkeypatch.setattr(
        client,
        "_request",
        lambda *args, **kwargs: {"unexpected": "object"},
    )

    with pytest.raises(
        HakikiHireAPIError,
        match="registry response was not a JSON list",
    ):
        client.get_registry_records()

    with pytest.raises(
        HakikiHireAPIError,
        match="registry-audit response was not a JSON list",
    ):
        client.get_registry_audit_history(1)
