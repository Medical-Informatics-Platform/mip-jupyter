# Architecture

## Runtime flow

```text
Jupyter notebook (mip-jupyter image)
  → mip Python client (installed package)
  → platform-backend (/services)
  → Exaflow
```

Notebooks never call Exaflow directly.

## Repository roles

| Area | Audience | Contents |
|------|----------|----------|
| `workspace/` | Production Jupyter users | `Welcome.ipynb`, examples, scratch (seeded into `/home/jovyan/work`) |
| `docs/user/` | Production Jupyter users | User docs (copied to workspace `docs/` at image build) |
| `docs/llm/` | AI agents | Task-scoped agent wiki (`AGENTS.md` bootstrap) |
| `python-client/` | Developers | `mip` package source and tests |
| `docker/` | Operators | Single-user and Hub image definitions |
| `dev/` | Local developers | JupyterLab runner with Codex/MCP |
| `docs/` (root) | Operators, developers | Architecture, release process, operators guide |

Deployment orchestration (Compose, Kubernetes, Keycloak wiring) lives in **`mip/deployment`**.

## Production workspace model

The single-user Docker image:

1. Installs `mip` from `python-client/` as a Python package during build.
2. Copies `workspace/` to `/opt/mip-workspace-template/` and `docs/user/` to `.../docs/`.
3. Copies `docs/llm/` and `AGENTS.md` to `/opt/mip-agent-docs/` (not exposed in the file browser).
4. On container start, seeds `/home/jovyan/work` from the template when `Welcome.ipynb` is absent.
5. Starts JupyterLab with root `/home/jovyan/work` and default URL `Welcome.ipynb`.

Deployment artifacts (Dockerfiles, Hub config, client source, agent wiki) are not copied into the user workspace.

## Local development

Developers run `uv run mip-notebook` (or `./run-local-llm-codex.sh`). The runner syncs `docs/user/` into `workspace/docs/`, sets `MIP_JUPYTER_ROOT` and JupyterLab `ServerApp.root_dir` to `workspace/` (production parity with `/home/jovyan/work`), and keeps agent docs / editable `python-client` on the repo via `MIP_AGENT_DOCS` and the uv environment.
