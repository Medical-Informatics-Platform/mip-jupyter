"""Public client facade for the MIP platform backend."""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlparse

from .exceptions import MipConfigurationError
from .display import HelpText
from .transport import Transport


def _read_token_from_file() -> str | None:
    for filename in ("mip_token", ".mip_token"):
        try:
            with open(filename, encoding="utf-8") as handle:
                token = handle.read().strip()
        except FileNotFoundError:
            continue
        if token:
            return token
    return None


def _env_base_url() -> str | None:
    return os.getenv("PLATFORM_BACKEND_URL") or os.getenv("MIP_BASE_URL")


def _env_token() -> str | None:
    return (
        os.getenv("PLATFORM_TOKEN")
        or os.getenv("MIP_TOKEN")
        or _read_token_from_file()
    )


def _require_https(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme == "https" or (
        parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1", "::1")
    ):
        return
    raise MipConfigurationError(f"Remote MIP URLs must use https:// (got {url}).")


class Client:
    """Entry point for catalog discovery, algorithm metadata, and execution."""

    def __init__(
        self,
        base_url: str,
        token: str | None = None,
        *,
        timeout: float = 30.0,
        hub_api_url: str | None = None,
        hub_api_token: str | None = None,
    ):
        self._transport = Transport(
            base_url=base_url,
            token=token,
            timeout=timeout,
            hub_api_url=hub_api_url,
            hub_api_token=hub_api_token,
        )

    @classmethod
    def from_env(cls) -> "Client":
        """Connect using environment variables.

        In the MIP notebook everything is preset. From your own computer set
        MIP_URL (the portal, e.g. https://host) and MIP_API_TOKEN (a JupyterHub
        API token with the custom:mip-platform-token permission).
        """
        mip_url = os.getenv("MIP_URL", "").rstrip("/")
        api_token = os.getenv("MIP_API_TOKEN")
        base_url = _env_base_url() or (f"{mip_url}/services" if mip_url else None)
        if not base_url:
            raise MipConfigurationError(
                "PLATFORM_BACKEND_URL, MIP_BASE_URL or MIP_URL is required to create Client.from_env()."
            )
        hub_api_url = os.getenv("JUPYTERHUB_API_URL") or (
            f"{mip_url}/notebook/hub/api" if mip_url else None
        )
        token = _env_token()
        if mip_url or api_token:
            if not api_token and not token:
                raise MipConfigurationError(
                    "MIP_API_TOKEN is required with MIP_URL. Create one on the "
                    "MIP portal at /notebook/hub/token."
                )
            for url in (base_url, hub_api_url):
                if url:
                    _require_https(url)
        timeout = float(os.getenv("PLATFORM_BACKEND_TIMEOUT", "30"))
        return cls(
            base_url=base_url,
            token=token,
            timeout=timeout,
            hub_api_url=hub_api_url,
            hub_api_token=api_token,
        )

    def catalog(self):
        from .catalog import Catalog

        return Catalog(self._transport)

    def algorithms(self):
        from .algorithms import AlgorithmRegistry

        return AlgorithmRegistry(self._transport)

    def experiments(self):
        return ExperimentRegistry(self._transport)

    def help(self) -> HelpText:
        from .display import show_help

        return show_help("Client")


class ExperimentRegistry:
    """Small internal-facing registry for experiment execution endpoints."""

    def __init__(self, transport: Transport):
        self._transport = transport

    def list(self) -> list[dict[str, Any]]:
        payload = self._transport.get("/experiments")
        if isinstance(payload, dict):
            payload = payload.get("experiments") or payload.get("items") or []
        if not isinstance(payload, list):
            return []
        return [item for item in payload if isinstance(item, dict)]

    def get(self, experiment_id: str) -> dict[str, Any]:
        payload = self._transport.get(f"/experiments/{experiment_id}")
        return payload if isinstance(payload, dict) else {}

    def delete(self, experiment_id: str) -> None:
        self._transport.delete(f"/experiments/{experiment_id}")
