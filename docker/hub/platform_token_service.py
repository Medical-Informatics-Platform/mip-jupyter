"""JupyterHub API handler that returns or refreshes the platform-backend OAuth token."""

from __future__ import annotations

import asyncio
from collections import defaultdict

from jupyterhub import orm
from jupyterhub.apihandlers.base import APIHandler
from tornado import web

from platform_token_utils import refresh_access_token, token_is_expired

PLATFORM_TOKEN_SCOPE = "custom:mip-platform-token"

_refresh_locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)


async def fresh_access_token(user) -> str | None:
    """Return the user's platform access token, refreshed first if it has expired.

    The Keycloak POST runs in a thread so it cannot stall the hub's event loop, and
    the per-user lock stops concurrent requests from spending one refresh token twice.
    """
    async with _refresh_locks[user.name]:
        auth_state = await user.get_auth_state() or {}
        token = auth_state.get("access_token")
        if token and token_is_expired(token):
            refreshed = await asyncio.to_thread(refresh_access_token, auth_state)
            if refreshed:
                token = refreshed
                await user.save_auth_state(auth_state)
        return token


class PlatformTokenHandler(APIHandler):
    """Return the platform-backend Bearer token of the requesting token's owner.

    Callers are user servers and users' own API tokens; both need PLATFORM_TOKEN_SCOPE.

    Uses APIHandler (in-process token auth) instead of HubAuthenticated because this
    endpoint is registered on the hub itself; HubAuthenticated would HTTP-call the
    hub API and deadlock the single-threaded event loop.
    """

    async def get(self) -> None:
        user = self.current_user
        if user is None:
            raise web.HTTPError(403, "Not authenticated")
        if isinstance(user, orm.Service):
            raise web.HTTPError(403, "Only user server tokens are supported")
        # Checked here, not with @needs_scope: custom scopes are only registered
        # when the hub starts, after this module is imported.
        if PLATFORM_TOKEN_SCOPE not in self.parsed_scopes:
            raise web.HTTPError(403, f"Token is missing the {PLATFORM_TOKEN_SCOPE} permission")

        access_token = await fresh_access_token(user)
        if not access_token:
            raise web.HTTPError(401, "No platform access token available")

        if token_is_expired(access_token):
            raise web.HTTPError(
                401,
                "Platform access token is expired and could not be refreshed. Re-login to JupyterHub.",
            )

        self.set_header("Content-Type", "application/json")
        self.write({"access_token": access_token})
