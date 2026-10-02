"""Public client facade for the MIP platform backend."""

from __future__ import annotations

import os
from typing import Any

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


class Client:
    """Entry point for catalog discovery, algorithm metadata, and execution."""

    def __init__(self, base_url: str, token: str | None = None, *, timeout: float = 30.0):
        self._transport = Transport(base_url=base_url, token=token, timeout=timeout)

    @classmethod
    def from_env(cls) -> "Client":
        base_url = _env_base_url()
        if not base_url:
            raise MipConfigurationError(
                "PLATFORM_BACKEND_URL or MIP_BASE_URL is required to create Client.from_env()."
            )
        timeout = float(os.getenv("PLATFORM_BACKEND_TIMEOUT", "30"))
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
