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
| `PLATFORM_BACKEND_TIMEOUT` | Request timeout in seconds (default `30`) |
| `PLATFORM_BACKEND_ALLOW_REDIRECTS` | Set to `1` to follow redirects |

## Local defaults

`uv run mip-notebook` sets `PLATFORM_BACKEND_URL` to `http://127.0.0.1:8080/services` unless already set.

Docker image (`docker/singleuser/Dockerfile`) defaults to `http://platform-backend:8080/services`.

## JupyterHub

Hub may inject `JUPYTERHUB_API_URL` and `JUPYTERHUB_API_TOKEN` for token refresh.

## Security

- Never commit real tokens or credentials.
- Never log `MIP_TOKEN`, `PLATFORM_TOKEN`, or cookie values.
- Codex shell excludes env vars matching `*PASSWORD*`, `*TOKEN*`, `*SECRET*`, `*COOKIE*`, `*SESSION*`.

## Source reference

Implementation: `python-client/mip/client.py` (`Client.from_env()`).

**Next file:** `01-onboarding.md` if the user is ready to run analysis.
