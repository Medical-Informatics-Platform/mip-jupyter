# mip-jupyter

`mip-jupyter` packages the MIP JupyterLab workspace and the `mip` Python
client used to run federated analyses through the MIP platform.

This repository contains:

- the production notebook workspace template
- user documentation and example notebooks
- the `mip` Python client source and tests
- Docker image definitions for single-user Jupyter and JupyterHub
- local development utilities for running the workspace from this checkout

## Runtime Model

Notebook code uses the `mip` Python client. The client talks to the MIP
platform backend under `/services`; notebooks do not call execution services
directly.

```text
Jupyter notebook -> mip Python client -> MIP platform backend -> federated execution
```

## Production Workspace

When Jupyter is launched from the MIP portal, users work in:

```text
/home/jovyan/work/
  Welcome.ipynb
  examples/
  docs/
  scratch/
```

The `mip` package is pre-installed and the platform connection is configured
for the session:

```python
import mip

client = mip.Client.from_env()
```

Recommended starting path:

1. Open `Welcome.ipynb` and run all cells.
2. Read `docs/quickstart.md` for the basic workflow.
3. Use `examples/feres_analysis.ipynb` as a reference analysis.
4. Save personal notebooks and experiments under `scratch/`.

The source for the user documentation is [`docs/user/`](docs/user/). It is
copied into `workspace/docs/` for local development and into
`/home/jovyan/work/docs/` in the production image.

## Local Development

Run JupyterLab from this checkout:

```bash
uv sync
uv run mip-notebook
```

The local runner opens JupyterLab at `127.0.0.1:8888` with token `dev`, rooted
at `workspace/` (same file tree as production `/home/jovyan/work`). By default
it opens `examples/feres_analysis.ipynb`, syncs `docs/user/` into
`workspace/docs/`, and sets `PLATFORM_BACKEND_URL` to
`http://127.0.0.1:8080/services` unless it is already configured.

Open a different notebook:

```bash
MIP_NOTEBOOK=Welcome.ipynb uv run mip-notebook
```

## Build and Test

Install the development environment (includes the `mip` client from
`python-client/`, installed editable):

```bash
uv sync --extra dev
```

Run the Python checks (the `mip_jupyter_dev` tests need `codex-acp` on `PATH`:
`npm install -g @zed-industries/codex-acp`):

```bash
uv run pytest mip_jupyter_dev python-client/tests -q
uv run python python-client/verify_script.py
```

Build the images from the repository root:

```bash
docker build -f docker/singleuser/Dockerfile -t mip-jupyter:latest .
docker build -f docker/hub/Dockerfile -t mip-jupyterhub:latest .
```

See [`docs/release-process.md`](docs/release-process.md) for release checks.

## Client Configuration

`Client.from_env()` reads:

| Variable | Purpose |
|----------|---------|
| `PLATFORM_BACKEND_URL` or `MIP_BASE_URL` | Platform backend base URL under `/services` |
| `PLATFORM_TOKEN` or `MIP_TOKEN` | Bearer token |
| `PLATFORM_BACKEND_TIMEOUT` | Request timeout in seconds; default is `30` |
| `PLATFORM_BACKEND_ALLOW_REDIRECTS` | Set to `1` to follow redirects |

JupyterHub deployments may also inject `JUPYTERHUB_API_URL` and
`JUPYTERHUB_API_TOKEN` for token refresh.

## Repository Map

| Path | Purpose |
|------|---------|
| `workspace/` | Notebook workspace template seeded into `/home/jovyan/work` |
| `docs/user/` | Canonical user documentation copied into the workspace |
| `python-client/` | `mip` package source and tests |
| `docker/` | Single-user and JupyterHub image definitions |
| `mip_jupyter_dev/` | Local JupyterLab runner and development utilities |
| `docs/architecture.md` | Runtime and packaging architecture |
| `docs/operators.md` | Integration notes for platform operators |
| `docs/repository-layout.md` | Detailed repository layout |

## Deployment Ownership

This repository builds the Jupyter workspace and images. Platform deployment,
Hub configuration, identity-provider wiring, and rollout orchestration are
owned by `mip/deployment`.

For integration details, see [`docs/operators.md`](docs/operators.md).
