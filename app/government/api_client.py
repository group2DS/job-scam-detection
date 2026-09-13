"""HTTP client used by the SafeHire government dashboard."""

from __future__ import annotations

import os
from typing import Any

import requests


DEFAULT_API_URL = "http://127.0.0.1:8000"


class SafeHireAPIError(Exception):
    """Raised when a SafeHire API request cannot be completed."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details


class SafeHireAPIClient:
    """Client for the SafeHire FastAPI service."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: int = 30,
        access_token: str | None = None,
    ) -> None:
        configured_url = (
            base_url
            or os.getenv("SAFEHIRE_API_BASE_URL")
            or DEFAULT_API_URL
        )

        self.base_url = configured_url.rstrip("/")
        self.timeout = timeout
        self.access_token = access_token
        self.session = requests.Session()

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        if self.access_token:
            headers["Authorization"] = "Bearer {}".format(
                self.access_token
            )

        return headers

    @staticmethod
    def _safe_json(response: requests.Response) -> Any:
        try:
            return response.json()
        except ValueError:
            return None

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        url = "{}{}".format(self.base_url, path)

        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=json_body,
                headers=self._headers(),
                timeout=self.timeout,
            )
        except requests.Timeout as exc:
            raise SafeHireAPIError(
                "The SafeHire API took too long to respond."
            ) from exc
        except requests.ConnectionError as exc:
            raise SafeHireAPIError(
                "The SafeHire API could not be reached."
            ) from exc
        except requests.RequestException as exc:
            raise SafeHireAPIError(
                "The SafeHire API request failed."
            ) from exc

        details = self._safe_json(response)

        if response.status_code == 401:
            if path == "/api/auth/login":
                message = "Invalid username or password."
            else:
                message = (
                    "Your session is invalid or has expired. "
                    "Sign in again."
                )

            raise SafeHireAPIError(
                message,
                status_code=401,
                details=details,
            )

        if response.status_code == 403:
            raise SafeHireAPIError(
                "You do not have permission to perform this action.",
                status_code=403,
                details=details,
            )

        if response.status_code == 404:
            raise SafeHireAPIError(
                "The requested resource could not be found.",
                status_code=404,
                details=details,
            )

        if response.status_code == 409:
            raise SafeHireAPIError(
                "The requested action conflicts with the current case state.",
                status_code=409,
                details=details,
            )

        if response.status_code == 422:
            raise SafeHireAPIError(
                "The request was rejected because some values were invalid.",
                status_code=422,
                details=details,
            )

        if response.status_code >= 500:
            raise SafeHireAPIError(
                "The SafeHire API encountered an internal error.",
                status_code=response.status_code,
                details=details,
            )

        if not response.ok:
            raise SafeHireAPIError(
                "The SafeHire API returned status {}.".format(
                    response.status_code
                ),
                status_code=response.status_code,
                details=details,
            )

        if response.status_code == 204:
            return {}

        if details is None:
            raise SafeHireAPIError(
                "The SafeHire API returned an invalid JSON response.",
                status_code=response.status_code,
            )

        return details

    def login(self, username: str, password: str) -> dict[str, Any]:
        if not username or not username.strip():
            raise ValueError("Username is required.")

        if not password:
            raise ValueError("Password is required.")

        result = self._request(
            method="POST",
            path="/api/auth/login",
            json_body={
                "username": username.strip(),
                "password": password,
            },
        )

        if not isinstance(result, dict):
            raise SafeHireAPIError(
                "The login response was not a JSON object."
            )

        access_token = result.get("access_token")
        reviewer = result.get("reviewer")

        if not isinstance(access_token, str) or not access_token.strip():
            raise SafeHireAPIError(
                "The login response did not contain an access token."
            )

        if not isinstance(reviewer, dict):
            raise SafeHireAPIError(
                "The login response did not contain a reviewer profile."
            )

        self.access_token = access_token.strip()
        return result

    def get_current_user(self) -> dict[str, Any]:
        result = self._request(
            method="GET",
            path="/api/auth/me",
        )

        if not isinstance(result, dict):
            raise SafeHireAPIError(
                "The reviewer profile response was not a JSON object."
            )

        return result

    def logout(self) -> None:
        self.access_token = None

    def health(self) -> dict[str, Any]:
        result = self._request(
            method="GET",
            path="/api/health",
        )

        if not isinstance(result, dict):
            raise SafeHireAPIError(
                "The health response was not a JSON object."
            )

        return result

    def get_cases(
        self,
        risk_level: str | None = None,
        review_status: str | None = None,
        is_overseas: bool | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        if limit < 1 or limit > 200:
            raise ValueError("limit must be between 1 and 200")

        params: dict[str, Any] = {"limit": limit}

        if risk_level:
            params["risk_level"] = risk_level

        if review_status:
            params["review_status"] = review_status

        if is_overseas is not None:
            params["is_overseas"] = is_overseas

        result = self._request(
            method="GET",
            path="/api/cases",
            params=params,
        )

        if not isinstance(result, list):
            raise SafeHireAPIError(
                "The case queue response was not a JSON list."
            )

        return result

    def get_stats(self) -> dict[str, Any]:
        result = self._request(
            method="GET",
            path="/api/cases/stats",
        )

        if not isinstance(result, dict):
            raise SafeHireAPIError(
                "The statistics response was not a JSON object."
            )

        return result

    def get_case(self, case_id: str) -> dict[str, Any]:
        if not case_id or not case_id.strip():
            raise ValueError("case_id is required")

        result = self._request(
            method="GET",
            path="/api/cases/{}".format(case_id.strip()),
        )

        if not isinstance(result, dict):
            raise SafeHireAPIError(
                "The case-detail response was not a JSON object."
            )

        return result

    def submit_decision(
        self,
        case_id: str,
        outcome: str,
        notes: str | None,
        reviewer: str,
    ) -> dict[str, Any]:
        if not case_id or not case_id.strip():
            raise ValueError("case_id is required")

        if not outcome or not outcome.strip():
            raise ValueError("outcome is required")

        if not reviewer or not reviewer.strip():
            raise ValueError("reviewer is required")

        payload = {
            "outcome": outcome.strip(),
            "notes": notes.strip() if notes else None,
            "reviewer": reviewer.strip(),
        }

        result = self._request(
            method="POST",
            path="/api/cases/{}/decision".format(case_id.strip()),
            json_body=payload,
        )

        if not isinstance(result, dict):
            raise SafeHireAPIError(
                "The decision response was not a JSON object."
            )

        return result
