"""HTTP client used by the SafeHire Government Dashboard."""

import os
from typing import Any, Dict, List, Optional

import requests


DEFAULT_API_URL = "http://127.0.0.1:8000"


class SafeHireAPIError(Exception):
    """Raised when the SafeHire API request cannot be completed."""

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


class SafeHireAPIClient:
    """Client for communicating with the SafeHire FastAPI service."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: int = 30,
        access_token: Optional[str] = None,
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

    def set_access_token(self, access_token: Optional[str]) -> None:
        """Set or clear the access token used by API requests."""
        self.access_token = access_token

    def logout(self) -> None:
        """Clear the locally stored bearer token."""
        self.set_access_token(None)

    def _headers(self) -> Dict[str, str]:
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

    @staticmethod
    def _error_detail(response_data: Any) -> Optional[str]:
        if not isinstance(response_data, dict):
            return None

        detail = response_data.get("detail")
        return detail if isinstance(detail, str) else None

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> Any:
        url = "{}{}".format(self.base_url, path)

        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=json_body,
                timeout=self.timeout,
                headers=self._headers(),
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

        response_data = self._safe_json(response)
        detail = self._error_detail(response_data)

        if response.status_code == 401:
            if path == "/api/auth/login":
                message = detail or "Invalid username or password."
            else:
                message = detail or (
                    "Your session is invalid or has expired. "
                    "Please sign in again."
                )

            raise SafeHireAPIError(
                message,
                status_code=401,
                details=response_data,
            )

        status_messages = {
            403: "You do not have permission to perform this action.",
            404: "The requested resource could not be found.",
            409: "The requested action conflicts with the current case state.",
            422: "The request was rejected because some values were invalid.",
            429: "Too many requests were made. Please try again later.",
        }

        if response.status_code in status_messages:
            raise SafeHireAPIError(
                detail or status_messages[response.status_code],
                status_code=response.status_code,
                details=response_data,
            )

        if response.status_code >= 500:
            raise SafeHireAPIError(
                "The SafeHire API encountered an internal error.",
                status_code=response.status_code,
                details=response_data,
            )

        if not response.ok:
            raise SafeHireAPIError(
                detail
                or "The SafeHire API returned status {}.".format(
                    response.status_code
                ),
                status_code=response.status_code,
                details=response_data,
            )

        if response.status_code == 204:
            return {}

        if response_data is None:
            raise SafeHireAPIError(
                "The SafeHire API returned an invalid JSON response.",
                status_code=response.status_code,
            )

        return response_data

    def health(self) -> Dict[str, Any]:
        result = self._request(
            method="GET",
            path="/api/health",
        )

        if not isinstance(result, dict):
            raise SafeHireAPIError(
                "The health response was not a JSON object."
            )

        return result

    def login(self, username: str, password: str) -> Dict[str, Any]:
        """Authenticate and retain the returned access token."""
        normalized_username = username.strip()

        if not normalized_username:
            raise ValueError("Username is required.")

        if not password:
            raise ValueError("Password is required.")

        result = self._request(
            method="POST",
            path="/api/auth/login",
            json_body={
                "username": normalized_username,
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

        self.set_access_token(access_token.strip())
        return result

    def get_current_user(self) -> Dict[str, Any]:
        result = self._request(
            method="GET",
            path="/api/auth/me",
        )

        if not isinstance(result, dict):
            raise SafeHireAPIError(
                "The user-profile response was not a JSON object."
            )

        return result

    def create_user(
        self,
        username: str,
        password: str,
        display_name: str,
        role: str = "reviewer",
    ) -> Dict[str, Any]:
        result = self._request(
            method="POST",
            path="/api/auth/users",
            json_body={
                "username": username.strip(),
                "password": password,
                "display_name": display_name.strip(),
                "role": role,
            },
        )

        if not isinstance(result, dict):
            raise SafeHireAPIError(
                "The create-user response was not a JSON object."
            )

        return result

    def get_destination_countries(self) -> List[str]:
        """Return destination countries available in referred cases."""
        result = self._request(
            method="GET",
            path="/api/cases/countries",
        )

        if not isinstance(result, list):
            raise SafeHireAPIError(
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
        review_status: Optional[str] = None,
        is_overseas: Optional[bool] = None,
        destination_country: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Return referred cases matching the supplied queue filters."""
        if limit < 1 or limit > 200:
            raise ValueError("limit must be between 1 and 200")

        if date_from and date_to and date_from > date_to:
            raise ValueError(
                "date_from must be on or before date_to"
            )

        params: Dict[str, Any] = {"limit": limit}

        if risk_level:
            params["risk_level"] = risk_level

        if review_status:
            params["review_status"] = review_status

        if is_overseas is not None:
            params["is_overseas"] = is_overseas

        if destination_country and destination_country.strip():
            params["destination_country"] = (
                destination_country.strip()
            )

        if date_from:
            params["date_from"] = date_from

        if date_to:
            params["date_to"] = date_to

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

    def get_stats(self) -> Dict[str, Any]:
        result = self._request(
            method="GET",
            path="/api/cases/stats",
        )

        if not isinstance(result, dict):
            raise SafeHireAPIError(
                "The statistics response was not a JSON object."
            )

        return result

    def get_case(self, case_id: str) -> Dict[str, Any]:
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
        notes: str,
        reviewer: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not case_id or not case_id.strip():
            raise ValueError("case_id is required")

        if not outcome or not outcome.strip():
            raise ValueError("outcome is required")

        payload: Dict[str, Any] = {
            "outcome": outcome.strip(),
            "notes": notes.strip() if notes else "",
        }

        if reviewer and reviewer.strip():
            payload["reviewer"] = reviewer.strip()

        result = self._request(
            method="POST",
            path="/api/cases/{}/decision".format(
                case_id.strip()
            ),
            json_body=payload,
        )

        if not isinstance(result, dict):
            raise SafeHireAPIError(
                "The decision response was not a JSON object."
            )

        return result
