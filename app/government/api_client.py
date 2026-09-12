import os
from typing import Any, Dict, List, Optional

import requests


DEFAULT_API_URL = "http://127.0.0.1:8000"


class SafeHireAPIError(Exception):
    """Raised when a SafeHire API request cannot be completed."""

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
    ) -> None:
        configured_url = (
            base_url
            or os.getenv("SAFEHIRE_API_BASE_URL")
            or DEFAULT_API_URL
        )

        self.base_url = configured_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()

    def _safe_json(self, response: requests.Response) -> Any:
        try:
            return response.json()
        except ValueError:
            return None

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
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
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

        if response.status_code == 404:
            raise SafeHireAPIError(
                "The requested resource could not be found.",
                status_code=404,
                details=response_data,
            )

        if response.status_code == 409:
            raise SafeHireAPIError(
                "The requested action conflicts with the current case state.",
                status_code=409,
                details=response_data,
            )

        if response.status_code == 422:
            raise SafeHireAPIError(
                "The request was rejected because some values were invalid.",
                status_code=422,
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
                "The SafeHire API returned status {}.".format(
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

    def get_cases(
        self,
        risk_level: Optional[str] = None,
        review_status: Optional[str] = None,
        is_overseas: Optional[bool] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        if limit < 1 or limit > 200:
            raise ValueError("limit must be between 1 and 200")

        params = {
            "limit": limit,
        }

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
        reviewer: str,
    ) -> Dict[str, Any]:
        if not case_id or not case_id.strip():
            raise ValueError("case_id is required")

        if not outcome or not outcome.strip():
            raise ValueError("outcome is required")

        if not reviewer or not reviewer.strip():
            raise ValueError("reviewer is required")

        payload = {
            "outcome": outcome.strip(),
            "notes": notes.strip() if notes else "",
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