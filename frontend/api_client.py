import json
import os
from typing import Any

import requests

DEFAULT_API_BASE_URL = "http://127.0.0.1:8000/api/v1"


class ApiClientError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None, payload: Any | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.payload = payload


class ApiClient:
    def __init__(self, base_url: str | None = None, timeout: tuple[float, float] = (5.0, 20.0)):
        self.base_url = (base_url or os.getenv("API_BASE_URL", DEFAULT_API_BASE_URL)).rstrip("/")
        self.timeout = timeout

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = f"/{path}"
        return f"{self.base_url}{path}"

    def request(self, method: str, path: str, *, params: dict[str, Any] | None = None, payload: Any = None, json: Any = None, timeout: tuple[float, float] | None = None):
        url = self._url(path)
        request_timeout = timeout or self.timeout
        try:
            response = requests.request(
                method.upper(),
                url,
                params=params,
                json=json if json is not None else payload,
                timeout=request_timeout,
            )
        except requests.exceptions.RequestException as exc:  # pragma: no cover - network path
            raise ApiClientError(f"API request failed: {exc}") from exc

        try:
            data = response.json()
        except ValueError:
            data = {}

        if response.status_code >= 400:
            detail = data.get("detail") if isinstance(data, dict) else None
            if isinstance(detail, list):
                message = "; ".join(str(item.get("msg") or item) for item in detail if isinstance(item, dict) or item is not None)
            elif isinstance(detail, dict):
                message = detail.get("msg") or detail.get("error") or "API request failed"
            else:
                message = str(detail) if detail else f"Request failed with HTTP {response.status_code}"
            raise ApiClientError(message, status_code=response.status_code, payload=data)

        return data

    def get(self, path: str, *, params: dict[str, Any] | None = None):
        return self.request("GET", path, params=params)

    def post(self, path: str, *, params: dict[str, Any] | None = None, json: Any | None = None):
        return self.request("POST", path, params=params, json=json)

    def patch(self, path: str, *, json: Any | None = None):
        return self.request("PATCH", path, json=json)

    def delete(self, path: str):
        return self.request("DELETE", path)


def get_api_client() -> ApiClient:
    return ApiClient()


def get_user_options(api: ApiClient) -> list[dict[str, Any]]:
    try:
        users = api.get("/users")
        return users.get("items", []) if isinstance(users, dict) else []
    except ApiClientError:
        return []
