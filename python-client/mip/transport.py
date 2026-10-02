"""Internal HTTP transport for platform-backend."""

from __future__ import annotations

import base64
import json
import os
import time
from typing import Any
from urllib.parse import urljoin

import requests

from .exceptions import MipBackendError


class Transport:
    """Small JSON transport used by the public client facade."""

    def __init__(
        self,
        base_url: str,
        token: str | None = None,
        *,
        timeout: float = 30.0,
        allow_redirects: bool | None = None,
    ):
        if not isinstance(base_url, str) or not base_url.strip():
            raise ValueError("base_url must be a non-empty string.")
        self.base_url = base_url.rstrip("/") + "/"
        self.token = token
        self.timeout = float(timeout)
        if allow_redirects is None:
            allow_redirects = os.getenv("PLATFORM_BACKEND_ALLOW_REDIRECTS", "0") in ("1", "true", "True")
        self.allow_redirects = bool(allow_redirects)
        self.session = requests.Session()
        if token:
            self.session.headers.update({"Authorization": f"Bearer {token}"})

    def get(self, path: str, params: dict | None = None) -> Any:
        return self._request("GET", path, params=params)

    def post(self, path: str, payload: dict) -> Any:
        return self._request("POST", path, json=payload)

    def delete(self, path: str) -> None:
        self._request("DELETE", path)

    def set_token(self, token: str | None) -> None:
        self.token = token
        if token:
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        else:
            self.session.headers.pop("Authorization", None)

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = self._url(path)
        self._raise_if_expired_token()
        try:
            response = self._request_once(method, url, **kwargs)
            if response.status_code == 401 and self._maybe_refresh_token_via_jupyterhub():
                response = self._request_once(method, url, **kwargs)
        except requests.RequestException as exc:
            raise MipBackendError(f"Backend request failed: {method} {url}: {exc}") from exc

        if 300 <= response.status_code < 400:
            location = response.headers.get("Location") if response.headers else None
            raise MipBackendError(
                "Backend request was redirected, likely because authentication is required. "
                f"Request: {method} {url}; status: {response.status_code}; location: {location}"
            )

        if response.status_code >= 400:
            details = self._error_details(response)
            raise MipBackendError(
                f"Backend request failed: {method} {url}; status: {response.status_code}; details: {details}"
            )

        if response.status_code == 204 or not (response.content or b"").strip():
            return {}

        try:
            return response.json()
        except ValueError as exc:
            preview = (response.text or "")[:200]
            raise MipBackendError(
                f"Backend returned non-JSON response for {method} {url}: {preview}"
            ) from exc

    def _request_once(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        return self.session.request(
            method,
            url,
            timeout=self.timeout,
            allow_redirects=self.allow_redirects,
            **kwargs,
        )

    def _url(self, path: str) -> str:
        safe_path = str(path or "").lstrip("/")
        return urljoin(self.base_url, safe_path)

    def _raise_if_expired_token(self) -> None:
        if not self.token:
            # Under the notebook operator the token is not in the pod env; the
            # hub hands it out on first use.
            self._maybe_refresh_token_via_jupyterhub()
            return
        if self._token_is_expired(self.token):
            if self._maybe_refresh_token_via_jupyterhub():
                return
            raise MipBackendError(
                "The API token is expired and could not be refreshed automatically. "
                "Re-login or restart the notebook server, or provide a fresh token."
            )

    def _maybe_refresh_token_via_jupyterhub(self) -> bool:
        api_url = os.getenv("JUPYTERHUB_API_URL", "").rstrip("/")
        api_token = os.getenv("JUPYTERHUB_API_TOKEN", "")
        if not api_url or not api_token:
            return False
        url = f"{api_url}/platform-token"
        try:
            response = requests.get(
                url,
                headers={"Authorization": f"token {api_token}"},
                timeout=min(self.timeout, 15.0),
                allow_redirects=False,
            )
        except requests.RequestException:
            return False
        if response.status_code != 200:
            return False
        try:
            data = response.json() if response.content else {}
        except ValueError:
            return False
        token = (data or {}).get("access_token")
        if not token or not isinstance(token, str):
            return False
        if self._token_is_expired(token):
            return False
        self.set_token(token)
        self._sync_token_env(token)
        return True

    def _sync_token_env(self, token: str) -> None:
        if os.getenv("JUPYTERHUB_API_URL") or "MIP_TOKEN" in os.environ:
            os.environ["MIP_TOKEN"] = token
        if "PLATFORM_TOKEN" in os.environ:
            os.environ["PLATFORM_TOKEN"] = token

    @staticmethod
    def _token_is_expired(token: str) -> bool:
        payload = Transport._decode_jwt_payload(token)
        exp = payload.get("exp")
        return isinstance(exp, (int, float)) and exp <= time.time()

    @staticmethod
    def _decode_jwt_payload(token: str) -> dict[str, Any]:
        parts = token.split(".")
        if len(parts) != 3:
            return {}
        payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
        try:
            decoded = base64.urlsafe_b64decode(payload_b64.encode("utf-8"))
            return json.loads(decoded.decode("utf-8"))
        except (ValueError, json.JSONDecodeError):
            return {}

    @staticmethod
    def _error_details(response: requests.Response) -> Any:
        try:
            return response.json()
        except ValueError:
            return (response.text or "")[:500]
