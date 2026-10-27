"""Sign in from your own computer: Keycloak device login (`mip login`) and token refresh.

The portal's backend names its Keycloak and the public client to use (`GET /auth-config`).
`mip login` runs the OAuth 2.0 device flow against it and keeps only the refresh token,
per portal, in CREDENTIALS_FILE; the client trades it for access tokens when it needs one.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import json
import os
import secrets
import tempfile
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

import requests

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None

from .exceptions import MipBackendError, MipConfigurationError, MipError

# A file, not an environment variable: programs started from your terminal (AI
# assistants included) do not inherit it.
CREDENTIALS_FILE = Path.home() / ".config" / "mip" / "credentials.json"
TIMEOUT = 15.0
DEVICE_GRANT = "urn:ietf:params:oauth:grant-type:device_code"


def require_https(url: str) -> None:
    parsed = urlparse(url)
    # requests would send user:password as Basic auth instead of the access token, and
    # messages that name the URL would show the password.
    if "@" in parsed.netloc:
        raise MipConfigurationError("Remote MIP URLs must not contain a user name or password.")
    if parsed.scheme == "https" or (
        parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1", "::1")
    ):
        return
    raise MipConfigurationError(
        f"Remote MIP URLs must use https:// (got {parsed.scheme}://{parsed.hostname})."
    )


def _load() -> dict[str, Any]:
    try:
        data = json.loads(CREDENTIALS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


@contextlib.contextmanager
def _locked():
    """Hold the credentials file across a read-modify-write, against other mip processes.

    ponytail: POSIX only (fcntl); on Windows concurrent writers still race, msvcrt.locking
    would cover them.
    """
    CREDENTIALS_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(CREDENTIALS_FILE.with_name(CREDENTIALS_FILE.name + ".lock"), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        if fcntl:
            fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)  # also releases the lock


def _save(data: dict[str, Any]) -> None:
    CREDENTIALS_FILE.parent.mkdir(parents=True, exist_ok=True)
    # mkstemp creates the file readable only by you; replace() swaps it in whole.
    fd, tmp = tempfile.mkstemp(dir=CREDENTIALS_FILE.parent, prefix=".credentials-")
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
    os.replace(tmp, CREDENTIALS_FILE)


# Key in the credentials file naming the portal `mip login` signed in to last; used when
# MIP_URL is not set.
DEFAULT_PORTAL = "default"


def is_signed_in(mip_url: str) -> bool:
    return isinstance(_load().get(mip_url), dict)


def default_portal() -> str | None:
    portal = _load().get(DEFAULT_PORTAL)
    return portal if isinstance(portal, str) else None


def _get_json(url: str, what: str, *, not_found: str | None = None) -> dict[str, Any]:
    try:
        response = requests.get(url, timeout=TIMEOUT, allow_redirects=False)
    except requests.RequestException as exc:
        raise MipBackendError(f"Could not reach {what} ({url}: {type(exc).__name__}).") from exc
    # Backends without the endpoint answer 401: it is behind their login.
    if response.status_code in (401, 404) and not_found:
        raise MipConfigurationError(not_found)
    try:
        data = response.json() if response.status_code == 200 else None
    except ValueError:
        data = None
    if not isinstance(data, dict):
        raise MipBackendError(f"Unexpected answer from {what} ({url}: status {response.status_code}).")
    return data


def _post(url: str, data: dict[str, str]) -> tuple[int, dict[str, Any]]:
    try:
        response = requests.post(url, data=data, timeout=TIMEOUT, allow_redirects=False)
    except requests.RequestException as exc:
        raise MipBackendError(f"Could not reach Keycloak ({url}: {type(exc).__name__}).") from exc
    try:
        body = response.json()
    except ValueError:
        body = {}
    return response.status_code, body if isinstance(body, dict) else {}


def _discover(backend_url: str) -> dict[str, str]:
    """The portal's laptop client and its Keycloak endpoints."""

    config = _get_json(
        f"{backend_url.rstrip('/')}/auth-config",
        "the MIP portal",
        not_found="This MIP portal does not offer sign-in from your own computer yet. Ask its operators.",
    )
    issuer, client_id = config.get("issuer"), config.get("clientId")
    if not isinstance(issuer, str) or not isinstance(client_id, str) or not issuer or not client_id:
        raise MipBackendError("The MIP portal sent an incomplete sign-in configuration.")
    require_https(issuer)
    oidc = _get_json(f"{issuer.rstrip('/')}/.well-known/openid-configuration", "Keycloak")
    endpoints = {
        key: oidc.get(key)
        for key in ("device_authorization_endpoint", "token_endpoint", "revocation_endpoint")
    }
    if oidc.get("issuer") != issuer or not all(endpoints.values()):
        raise MipBackendError(f"Keycloak at {issuer} does not offer sign-in from a device.")
    for url in endpoints.values():
        require_https(url)
    return {"client_id": client_id, **endpoints}


def _entry(endpoints: dict[str, str], refresh_token: str) -> dict[str, str]:
    return {
        "client_id": endpoints["client_id"],
        "token_endpoint": endpoints["token_endpoint"],
        "revocation_endpoint": endpoints["revocation_endpoint"],
        "refresh_token": refresh_token,
    }


def _renew(entry: dict[str, str]) -> dict[str, Any]:
    """Refresh-token grant; returns Keycloak's answer with a new access token."""

    status, tokens = _post(
        entry["token_endpoint"],
        {"grant_type": "refresh_token", "refresh_token": entry["refresh_token"], "client_id": entry["client_id"]},
    )
    if status != 200 or not isinstance(tokens.get("access_token"), str):
        if tokens.get("error") == "invalid_grant":
            raise MipBackendError(
                "Your MIP token has expired or was revoked. Create a new one on the portal's "
                "account page, or run `mip login`."
            )
        raise MipBackendError(f"Could not renew MIP access with Keycloak ({tokens.get('error') or status}).")
    return tokens


def login(
    mip_url: str,
    backend_url: str,
    *,
    show: Callable[[str], None],
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Sign in with the device flow and save the refresh token for mip_url."""

    endpoints = _discover(backend_url)
    client_id = endpoints["client_id"]
    # PKCE: Keycloak requires it on device sign-in when the client enforces it.
    verifier = secrets.token_urlsafe(32)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    # offline_access: the sign-in outlives the browser session, for as long as the
    # Keycloak client allows (about 30 days).
    status, device = _post(
        endpoints["device_authorization_endpoint"],
        {
            "client_id": client_id,
            "scope": "openid offline_access",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        },
    )
    if status != 200 or not device.get("device_code") or not device.get("user_code"):
        raise MipBackendError(f"Keycloak refused the sign-in request ({device.get('error') or status}).")
    link = device.get("verification_uri_complete") or device.get("verification_uri")
    show(
        f"To sign in to {mip_url}, open this link in a browser:\n\n    {link}\n\n"
        f"Check that the page shows the code {device['user_code']}, then approve.\n"
        "Never approve a code that someone else sent you."
    )

    interval = float(device.get("interval") or 5)
    deadline = time.monotonic() + float(device.get("expires_in") or 600)
    while time.monotonic() < deadline:
        sleep(interval)
        status, tokens = _post(
            endpoints["token_endpoint"],
            {
                "grant_type": DEVICE_GRANT,
                "device_code": device["device_code"],
                "client_id": client_id,
                "code_verifier": verifier,
            },
        )
        if status == 200 and tokens.get("refresh_token"):
            break
        error = tokens.get("error")
        if error == "authorization_pending":
            continue
        if error == "slow_down":
            interval += 5
            continue
        raise MipBackendError(f"Sign-in failed ({error or status}). Run `mip login` again.")
    else:
        raise MipBackendError("Sign-in timed out. Run `mip login` again.")

    return _replace(mip_url, _entry(endpoints, tokens["refresh_token"]))


def _session_id(token: str) -> str | None:
    """Keycloak's session id (sid) in a refresh token; None when it cannot be read."""
    parts = token.split(".")
    if len(parts) != 3:
        return None
    try:
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4)))
    except ValueError:
        return None
    sid = payload.get("sid") if isinstance(payload, dict) else None
    return sid if isinstance(sid, str) else None


def _replace(mip_url: str, entry: dict[str, str]) -> dict[str, Any]:
    """Save a new sign-in for mip_url and revoke the one it replaces, so re-login rotates."""

    with _locked():
        data = _load()
        old = data.get(mip_url)
        data[mip_url] = entry
        data[DEFAULT_PORTAL] = mip_url
        _save(data)
    result: dict[str, Any] = {"ok": True, "signed_in_to": mip_url, "saved": str(CREDENTIALS_FILE)}
    # Only another Keycloak session: the same one (a token pasted again) must stay alive.
    old_sid = _session_id(old["refresh_token"]) if old else None
    if old_sid and old_sid != _session_id(entry["refresh_token"]):
        result["previous_revoked"] = _revoke(old)
    return result


def save_token(mip_url: str, backend_url: str, refresh_token: str) -> dict[str, Any]:
    """Check a token created on the portal's account page and save it for mip_url."""

    entry = _entry(_discover(backend_url), refresh_token.strip())
    tokens = _renew(entry)
    entry["refresh_token"] = tokens.get("refresh_token") or entry["refresh_token"]
    return _replace(mip_url, entry)


def access_token(mip_url: str) -> str:
    """Trade the saved refresh token for a fresh access token."""

    entry = _load().get(mip_url)
    if not entry:
        raise MipConfigurationError(f"You are not signed in to {mip_url}. Run `mip login`.")
    tokens = _renew(entry)
    # Keycloak may rotate the refresh token. Save it only over the sign-in it came from: a
    # `mip login` or `mip logout` that ran meanwhile wins (login revokes the old session).
    new_refresh = tokens.get("refresh_token")
    if new_refresh and new_refresh != entry["refresh_token"]:
        with _locked():
            data = _load()
            current = data.get(mip_url)
            if isinstance(current, dict) and current.get("refresh_token") == entry["refresh_token"]:
                current["refresh_token"] = new_refresh
                _save(data)
    return tokens["access_token"]


def env_token_refresher(backend_url: str, refresh_token: str) -> Callable[[], str]:
    """Access tokens from a token given in MIP_API_TOKEN, for programs with nowhere to save one.

    A refresh token that Keycloak rotates is kept in memory only; the variable keeps
    working as long as the realm does not revoke used refresh tokens (the default).
    """

    entry: dict[str, str] = {}

    def refresh() -> str:
        if not entry:
            entry.update(_entry(_discover(backend_url), refresh_token.strip()))
        tokens = _renew(entry)
        entry["refresh_token"] = tokens.get("refresh_token") or entry["refresh_token"]
        return tokens["access_token"]

    return refresh


def _revoke(entry: dict[str, str]) -> bool:
    try:
        status, _ = _post(
            entry["revocation_endpoint"],
            {"token": entry["refresh_token"], "token_type_hint": "refresh_token", "client_id": entry["client_id"]},
        )
    except MipBackendError:
        return False
    return status == 200


def logout(mip_url: str, backend_url: str, env_token: str | None = None) -> dict[str, Any]:
    """Revoke and forget the saved sign-in, and revoke the token in MIP_API_TOKEN if set."""

    result: dict[str, Any] = {"ok": True}
    # Forget first: revoking needs Keycloak, which may be unreachable.
    with _locked():
        data = _load()
        entry = data.pop(mip_url, None)
        default = data.pop(DEFAULT_PORTAL, None) if data.get(DEFAULT_PORTAL) == mip_url else None
        if entry is not None or default is not None:
            _save(data)
    if entry is not None:
        result["revoked"] = _revoke(entry)
    elif not env_token:
        result["signed_in"] = False
    if env_token:
        try:
            result["env_token_revoked"] = _revoke(_entry(_discover(backend_url), env_token.strip()))
        except MipError:
            result["env_token_revoked"] = False
        result["note"] = "Remove MIP_API_TOKEN from your environment."
    return result
