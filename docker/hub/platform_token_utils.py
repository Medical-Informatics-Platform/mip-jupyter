"""Pure helpers for platform token expiry and refresh."""

from __future__ import annotations

import base64
import json
import os
import time
from typing import Any

import requests


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def normalize_memory(value: str) -> str:
    """Convert Kubernetes quantities (Gi/Mi) to JupyterHub/KubeSpawner format (G/M)."""
    normalized = str(value or "").strip()
    if normalized.endswith("Gi"):
        return f"{normalized[:-2]}G"
    if normalized.endswith("Mi"):
        return f"{normalized[:-2]}M"
    if normalized.endswith("Ki"):
        return f"{normalized[:-2]}K"
    if normalized.endswith("Ti"):
        return f"{normalized[:-2]}T"
    return normalized


def normalize_cpu(value: str) -> float:
    """Convert Kubernetes CPU quantities (500m) to JupyterHub float cores (0.5)."""
    normalized = str(value or "").strip()
    if normalized.endswith("m"):
        return float(normalized[:-1]) / 1000.0
    return float(normalized)


def keycloak_realm_base() -> str:
    auth_url = env("KEYCLOAK_AUTH_URL", "https://iam.ebrains.eu/auth/").rstrip("/")
    realm = env("KEYCLOAK_REALM", "MIP")
    return f"{auth_url}/realms/{realm}"


def decode_jwt_exp(token: str) -> float | None:
    parts = token.split(".")
    if len(parts) != 3:
        return None
    payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        decoded = base64.urlsafe_b64decode(payload_b64.encode("utf-8"))
        payload = json.loads(decoded.decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        return None
    exp = payload.get("exp")
    return float(exp) if isinstance(exp, (int, float)) else None


def token_is_expired(token: str, *, skew_seconds: int = 30) -> bool:
    exp = decode_jwt_exp(token)
    if exp is None:
        return False
    return exp <= (time.time() + skew_seconds)


def refresh_access_token(auth_state: dict[str, Any]) -> str | None:
    refresh_token = auth_state.get("refresh_token")
    if not refresh_token:
        return None

    client_id = env("KEYCLOAK_CLIENT_ID")
    client_secret = env("KEYCLOAK_CLIENT_SECRET")
    if not client_id or not client_secret:
        return None

    token_url = f"{keycloak_realm_base()}/protocol/openid-connect/token"
    try:
        response = requests.post(
            token_url,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
            },
            timeout=15,
        )
    except requests.RequestException:
        return None

    if response.status_code != 200:
        return None

    try:
        payload = response.json()
    except ValueError:
        return None

    access_token = payload.get("access_token")
    if not access_token or not isinstance(access_token, str):
        return None
    if token_is_expired(access_token):
        return None

    auth_state["access_token"] = access_token
    if payload.get("refresh_token"):
        auth_state["refresh_token"] = payload["refresh_token"]
    return access_token
