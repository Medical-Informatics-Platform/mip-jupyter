# Environment and Backend Configuration

**Read when:** The user asks how `Client.from_env()` works, which env vars to set, or how notebooks reach the backend.

**Skip if:** The task is purely notebook editing via MCP (`04-jupyter-mcp.md`).

## Architecture

```text
Jupyter notebook → mip Python client → platform-backend (/services) → Exaflow
```

Notebooks never call Exaflow directly.

## `Client.from_env()` reads

| Variable | Purpose |
|----------|---------|
| `PLATFORM_BACKEND_URL` or `MIP_BASE_URL` | Backend base URL, e.g. `http://127.0.0.1:8080/services` |
| `PLATFORM_TOKEN` or `MIP_TOKEN` | Bearer token for platform-backend |
| `MIP_URL` | Remote only: portal base `https://<host>`; derives backend `{MIP_URL}/services` unless `PLATFORM_BACKEND_URL` / `MIP_BASE_URL` is set (same host only). Access comes from `MIP_API_TOKEN` or a `mip login` sign-in (Keycloak), never from `MIP_TOKEN`. Defaults to the portal `mip login` signed in to last |
| `MIP_API_TOKEN` | Remote only: token created on the portal's account page (a Keycloak offline token); renewed in memory; takes precedence over `mip login` |
| `PLATFORM_BACKEND_TIMEOUT` | Request timeout in seconds (default `30`) |
| `PLATFORM_BACKEND_ALLOW_REDIRECTS` | Set to `1` to follow redirects |

## Local defaults

`uv run mip-notebook` sets `PLATFORM_BACKEND_URL` to `http://127.0.0.1:8080/services` unless already set.

Docker image (`docker/singleuser/Dockerfile`) defaults to `http://platform-backend:8080/services`.

## JupyterHub

Hub may inject `JUPYTERHUB_API_URL` and `JUPYTERHUB_API_TOKEN` for token refresh.
The client fetches platform tokens from `{JUPYTERHUB_API_URL}/platform-token`, which
answers only the user's own servers (their `JUPYTERHUB_API_TOKEN`). Hub 403 = any other
token, including ones users create on `/hub/token`; hub 401 = no stored platform token
(user must open the Notebook page to sign in).

## Own computer (remote)

User guide: `docs/user/remote-access.md`. `pip install mip-client`, then either
create a token on the portal's account page and run `mip login --token https://<host>` (or set
`MIP_URL` and `MIP_API_TOKEN`), or run `mip login https://<host>` for the device flow in a browser.
The portal signed in to last is remembered in the credentials file and used when `MIP_URL` is unset
(never when `PLATFORM_BACKEND_URL`/`MIP_BASE_URL` is set, as in the notebook). Both use the public Keycloak client named by
`{backend}/auth-config` and keep a refresh token per portal in `~/.config/mip/credentials.json`;
the client renews access tokens itself (code: `mip/keycloak.py`). `mip logout` revokes them.
Remote URLs must be `https://` (localhost may use `http://`).

## Security

- Never commit real tokens or credentials.
- Never log `MIP_TOKEN`, `PLATFORM_TOKEN`, or cookie values.
- Codex shell excludes env vars matching `*PASSWORD*`, `*TOKEN*`, `*SECRET*`, `*COOKIE*`, `*SESSION*`.

## Source reference

Implementation: `python-client/mip/client.py` (`Client.from_env()`).

**Next file:** `01-onboarding.md` if the user is ready to run analysis.
