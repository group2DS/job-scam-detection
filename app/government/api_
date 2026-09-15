"""HTTP client for the Hakiki Hire Government Dashboard."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import requests

DEFAULT_API_URL = "http://127.0.0.1:8000"


class HakikiHireAPIError(Exception):
    """Raised when a Hakiki Hire API request cannot be completed."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details


class HakikiHireAPIClient:
    """Client for the Hakiki Hire FastAPI service."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: int = 30,
        access_token: Optional[str] = None,
    ) -> None:
        configured_url = (
            base_url
            or os.getenv("HAKIKI_HIRE_API_BASE_URL")
            or DEFAULT_API_URL
        )
        self.base_url = configured_url.rstrip("/")
        self.timeout = timeout
        self.access_token = access_token
        self.session = requests.Session()

    def set_access_token(self, access_token: Optional[str]) -> None:
        self.access_token = access_token

    def logout(self) -> None:
        self.set_access_token(None)

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    @staticmethod
    def _safe_json(response: requests.Response) -> Any:
        try:
            return response.json()
        except ValueError:
            return None

    @staticmethod
    def _detail(data: Any) -> Optional[str]:
        if not isinstance(data, dict):
            return None
        detail = data.get("detail")
        return detail if isinstance(detail, str) else None

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> Any:
        try:
            response = self.session.request(
                method=method,
                url=f"{self.base_url}{path}",
                params=params,
                json=json_body,
                timeout=self.timeout,
                headers=self._headers(),
            )
        except requests.Timeout as exc:
            raise HakikiHireAPIError(
                "The Hakiki Hire API took too long to respond."
            ) from exc
        except requests.ConnectionError as exc:
            raise HakikiHireAPIError(
                "The Hakiki Hire API could not be reached."
            ) from exc
        except requests.RequestException as exc:
            raise HakikiHireAPIError(
                "The Hakiki Hire API request failed."
            ) from exc

        data = self._safe_json(response)
        detail = self._detail(data)

        if response.status_code == 401:
            message = (
                detail or "Invalid username or password."
                if path == "/api/auth/login"
                else detail
                or "Your session is invalid or has expired. Please sign in again."
            )
            raise HakikiHireAPIError(message, 401, data)

        default_messages = {
            403: "You do not have permission to perform this action.",
            404: "The requested resource could not be found.",
            409: "The requested action conflicts with the current state.",
            422: "The request contains invalid values.",
            429: "Too many requests were made. Please try again later.",
        }
        if response.status_code in default_messages:
            raise HakikiHireAPIError(
                detail or default_messages[response.status_code],
                response.status_code,
                data,
            )
        if response.status_code >= 500:
            raise HakikiHireAPIError(
                "The Hakiki Hire API encountered an internal error.",
                response.status_code,
                data,
            )
        if not response.ok:
            raise HakikiHireAPIError(
                detail
                or f"The Hakiki Hire API returned status {response.status_code}.",
                response.status_code,
                data,
            )
        if response.status_code == 204:
            return {}
        if data is None:
            raise HakikiHireAPIError(
                "The Hakiki Hire API returned an invalid JSON response.",
                response.status_code,
            )
        return data

    @staticmethod
    def _require_dict(value: Any, message: str) -> Dict[str, Any]:
        if not isinstance(value, dict):
            raise HakikiHireAPIError(message)
        return value

    def health(self) -> Dict[str, Any]:
        return self._require_dict(
            self._request("GET", "/api/health"),
            "The health response was not a JSON object.",
        )

    def login(self, username: str, password: str) -> Dict[str, Any]:
        username = username.strip()
        if not username:
            raise ValueError("Username is required.")
        if not password:
            raise ValueError("Password is required.")
        result = self._require_dict(
            self._request(
                "POST",
                "/api/auth/login",
                json_body={"username": username, "password": password},
            ),
            "The login response was not a JSON object.",
        )
        token = result.get("access_token")
        reviewer = result.get("reviewer")
        if not isinstance(token, str) or not token.strip():
            raise HakikiHireAPIError(
                "The login response did not contain an access token."
            )
        if not isinstance(reviewer, dict):
            raise HakikiHireAPIError(
                "The login response did not contain a reviewer profile."
            )
        self.set_access_token(token.strip())
        return result

    def get_current_user(self) -> Dict[str, Any]:
        return self._require_dict(
            self._request("GET", "/api/auth/me"),
            "The user-profile response was not a JSON object.",
        )

    def get_users(self) -> List[Dict[str, Any]]:
        result = self._request("GET", "/api/auth/users")
        if not isinstance(result, list):
            raise HakikiHireAPIError(
                "The user-list response was not a JSON list."
            )
        return result

    def create_reviewer(
        self,
        username: str,
        password: str,
        display_name: str,
        role: str = "reviewer",
        is_active: bool = True,
    ) -> Dict[str, Any]:
        username = username.strip().lower()
        display_name = display_name.strip()
        if len(username) < 3:
            raise ValueError("Username must contain at least 3 characters.")
        if not display_name:
            raise ValueError("Display name is required.")
        if len(password) < 10:
            raise ValueError("Password must contain at least 10 characters.")
        if role not in {"admin", "reviewer"}:
            raise ValueError("Role must be admin or reviewer.")
        return self._require_dict(
            self._request(
                "POST",
                "/api/auth/users",
                json_body={
                    "username": username,
                    "password": password,
                    "display_name": display_name,
                    "role": role,
                    "is_active": bool(is_active),
                },
            ),
            "The create-user response was not a JSON object.",
        )

    def update_user_status(
        self,
        user_id: int,
        is_active: bool,
    ) -> Dict[str, Any]:
        if not isinstance(user_id, int) or user_id < 1:
            raise ValueError("A valid user_id is required.")
        return self._require_dict(
            self._request(
                "PATCH",
                f"/api/auth/users/{user_id}/status",
                json_body={"is_active": bool(is_active)},
            ),
            "The user-status response was not a JSON object.",
        )

    def update_user_role(
        self,
        user_id: int,
        role: str,
    ) -> Dict[str, Any]:
        if not isinstance(user_id, int) or user_id < 1:
            raise ValueError("A valid user_id is required.")
        if role not in {"admin", "reviewer"}:
            raise ValueError("Role must be admin or reviewer.")
        return self._require_dict(
            self._request(
                "PATCH",
                f"/api/auth/users/{user_id}/role",
                json_body={"role": role},
            ),
            "The user-role response was not a JSON object.",
        )

    def get_destination_countries(self) -> List[str]:
        """Return destination countries available to dashboard filters."""
        result = self._request("GET", "/api/cases/countries")
        if not isinstance(result, list):
            raise HakikiHireAPIError(
                "The destination-country response was not a JSON list."
            )
        return [
            str(country).strip()
            for country in result
            if str(country).strip()
        ]

    def get_cases(
        self,
        risk_level: Optional[str] = None,
        verification_status: Optional[str] = None,
        review_status: Optional[str] = None,
        is_overseas: Optional[bool] = None,
        destination_country: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        if limit < 1 or limit > 200:
            raise ValueError("limit must be between 1 and 200")
        if date_from and date_to and str(date_from) > str(date_to):
            raise ValueError("date_from must be on or before date_to")

        params: Dict[str, Any] = {"limit": limit}
        optional = {
            "risk_level": risk_level,
            "verification_status": verification_status,
            "review_status": review_status,
            "destination_country": destination_country,
            "date_from": date_from,
            "date_to": date_to,
        }
        for key, value in optional.items():
            if value is not None and str(value).strip():
                params[key] = value
        if is_overseas is not None:
            params["is_overseas"] = is_overseas

        result = self._request("GET", "/api/cases", params=params)
        if not isinstance(result, list):
            raise HakikiHireAPIError(
                "The case queue response was not a JSON list."
            )
        return result

    def get_stats(self) -> Dict[str, Any]:
        return self._require_dict(
            self._request("GET", "/api/cases/stats"),
            "The statistics response was not a JSON object.",
        )

    def get_case(self, case_id: str) -> Dict[str, Any]:
        if not case_id or not case_id.strip():
            raise ValueError("case_id is required")
        return self._require_dict(
            self._request("GET", f"/api/cases/{case_id.strip()}"),
            "The case-detail response was not a JSON object.",
        )

    def submit_decision(
        self,
        case_id: str,
        outcome: str,
        notes: str,
        reviewer: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not case_id or not case_id.strip():
            raise ValueError("case_id is required")
        if not outcome or not outcome.strip():
            raise ValueError("outcome is required")
        if reviewer is None or not str(reviewer).strip():
            raise ValueError("reviewer is required")

        payload = {
            "outcome": outcome.strip(),
            "notes": notes.strip() if notes else "",
            "reviewer": str(reviewer).strip(),
        }
        return self._require_dict(
            self._request(
                "POST",
                f"/api/cases/{case_id.strip()}/decision",
                json_body=payload,
            ),
            "The decision response was not a JSON object.",
        )
