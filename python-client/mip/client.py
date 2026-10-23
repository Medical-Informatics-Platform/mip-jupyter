"""Public client facade for the MIP platform backend."""

from __future__ import annotations

import os
from typing import Any, Callable
from urllib.parse import urlparse

from . import keycloak
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


def _origin(url: str) -> tuple[str, str | None, int | None]:
    parsed = urlparse(url)
    return parsed.scheme, parsed.hostname, parsed.port or {"http": 80, "https": 443}.get(parsed.scheme)


def remote_urls() -> tuple[str, str] | None:
    """(MIP_URL, backend URL) when connecting from your own computer, else None."""

    mip_url = os.getenv("MIP_URL", "").rstrip("/")
    if not mip_url:
        return None
    base_url = _env_base_url() or f"{mip_url}/services"
    for url in (mip_url, base_url):
        keycloak.require_https(url)
    # Your access token must only reach the MIP_URL host: a leftover
    # PLATFORM_BACKEND_URL or MIP_BASE_URL may point at another one.
    if _origin(mip_url) != _origin(base_url):
        hosts = ", ".join(f"{scheme}://{host}:{port}" for scheme, host, port in (_origin(mip_url), _origin(base_url)))
        raise MipConfigurationError(
            f"MIP_URL, PLATFORM_BACKEND_URL and MIP_BASE_URL must point at the same MIP portal "
            f"(got {hosts}). Unset the ones left from another setup."
        )
    return mip_url, base_url


class Client:
    """Entry point for catalog discovery, algorithm metadata, and execution."""

    def __init__(
        self,
        base_url: str,
        token: str | None = None,
        *,
        timeout: float = 30.0,
        refresh: Callable[[], str] | None = None,
    ):
        self._transport = Transport(base_url=base_url, token=token, timeout=timeout, refresh=refresh)

    @classmethod
    def from_env(cls) -> "Client":
        """Connect using environment variables.

        In the MIP notebook everything is preset. From your own computer set MIP_URL
        (the portal, e.g. https://host) and either sign in once with `mip login`, or set
        MIP_API_TOKEN to a token created on the portal's account page.
        """
        timeout = float(os.getenv("PLATFORM_BACKEND_TIMEOUT", "30"))
        remote = remote_urls()
        env_token = os.getenv("MIP_API_TOKEN")
        if env_token and not remote:
            raise MipConfigurationError("MIP_API_TOKEN needs MIP_URL, the address of your MIP portal.")
        if remote:
            mip_url, base_url = remote
            # Leftover MIP_TOKEN/PLATFORM_TOKEN or a token file may belong to another
            # federation and must not reach this host.
            if env_token:
                return cls(base_url, timeout=timeout, refresh=keycloak.env_token_refresher(base_url, env_token))
            if not keycloak.is_signed_in(mip_url):
                raise MipConfigurationError(
                    f"You are not signed in to {mip_url}. Run `mip login`, or set MIP_API_TOKEN "
                    "to a token created on the portal's account page."
                )
            return cls(base_url, timeout=timeout, refresh=lambda: keycloak.access_token(mip_url))
        base_url = _env_base_url()
        if not base_url:
            raise MipConfigurationError(
                "PLATFORM_BACKEND_URL, MIP_BASE_URL or MIP_URL is required to create Client.from_env()."
            )
        return cls(base_url=base_url, token=_env_token(), timeout=timeout)

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
