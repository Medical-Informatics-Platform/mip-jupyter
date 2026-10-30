"""Notebook names and env shared by both operator spawners.

Imports no Kubernetes client: the ``operator-api`` hub has no Kubernetes
credential and must not load one.
"""

from __future__ import annotations

import importlib.util
import os
import re

TOKEN_ENV = ("JUPYTERHUB_API_TOKEN", "JPY_API_TOKEN")
# Must match the CRD validation rule on Notebook.spec.env.
ALLOWED_ENV = re.compile(r"^(JUPYTERHUB|JPY)_[A-Z0-9_]+$")
SLUG_MAX = 48


def _load_slugs():
    # kubespawner/__init__.py imports KubeSpawner, and with it kubernetes_asyncio;
    # load slugs.py (stdlib + escapism) on its own instead.
    package = importlib.util.find_spec("kubespawner")
    path = os.path.join(package.submodule_search_locations[0], "slugs.py")
    spec = importlib.util.spec_from_file_location("_mip_kubespawner_slugs", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_slugs = _load_slugs()


def notebook_env(env: dict[str, str]) -> dict[str, str]:
    """Keep only what a Notebook may carry; the token goes through the Secret."""
    return {k: v for k, v in env.items() if ALLOWED_ENV.match(k) and k not in TOKEN_ENV}


def notebook_name(user: str, server: str) -> str:
    # KubeSpawner's pod name, jupyter-{user_server} ("safe" slugs): a name
    # kept as-is never contains "--", so it cannot equal an escaped one
    # ending in "---<hash>". At most 56 chars; the CRD allows 57.
    user_slug = _slugs.safe_slug(user, max_length=SLUG_MAX)
    server_slug = _slugs.safe_slug(server, max_length=SLUG_MAX) if server else ""
    if len(user_slug) + len(server_slug) + 2 > SLUG_MAX:
        return "jupyter-" + _slugs.multi_slug([user, server or ""], max_length=SLUG_MAX)
    return "jupyter-" + (f"{user_slug}--{server_slug}" if server_slug else user_slug)
