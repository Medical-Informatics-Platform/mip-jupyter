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
| `workspace/` | Production Jupyter users | `Welcome.ipynb` (seeded into `/home/jovyan/work`) |
| `docs/user/` | Production Jupyter users | User docs (copied to workspace `docs/` at image build) |
| `python-client/mip/agent_docs/` | AI agents | Task-scoped agent wiki (`AGENTS.md` bootstrap) |
| `python-client/` | Developers | `mip-client` package (import `mip`), source and tests |
| `docker/` | Operators | Single-user and Hub image definitions |
| `dev/` | Local developers | JupyterLab runner with Codex/MCP |
| `docs/` (root) | Operators, developers | Architecture, release process, operators guide |

Deployment orchestration (Compose, Kubernetes, Keycloak wiring) lives in **`mip/deployment`**.

## Production workspace model

The single-user Docker image:

1. Installs `mip` from `python-client/` as a Python package during build.
2. Copies `workspace/` to `/opt/mip-workspace-template/` and `docs/user/` to `.../docs/`.
3. Copies `python-client/mip/agent_docs/` and `AGENTS.md` to `/opt/mip-agent-docs/` (not exposed in the file browser).
4. On container start, seeds `/home/jovyan/work` from the template when `Welcome.ipynb` is absent.
5. Starts JupyterLab with root `/home/jovyan/work` and default URL `Welcome.ipynb`.

Deployment artifacts (Dockerfiles, Hub config, client source, agent wiki) are not copied into the user workspace.

The examples are not in the image either. They live in
[`mip-examples`](https://github.com/Medical-Informatics-Platform/mip-examples). In MIP
clusters each federation namespace has a claim `mip-examples` and a `mip-examples-sync`
CronJob that checks `master` every minute and, when it moved, clones it onto that claim and
swaps it in atomically; the notebook operator mounts the claim read-only at
`/home/jovyan/work/.mip-examples` (`EXAMPLES_CLAIM`, see
[notebook-operator.md](notebook-operator.md)). The infra side is
[`common/examples`](https://github.com/Medical-Informatics-Platform/mip-infra-staging/tree/main/common/examples)
in mip-infra-staging (production mip-infra follows). On start, the entrypoint links `examples` to `.mip-examples/examples`.
Without the mount (KubeSpawner, local runs) it only removes a dangling link: a
real `examples/` copied by older images stays as a frozen copy, and a new home
has no `examples/`. A merge to
mip-examples reaches running notebooks in about a minute, with no image build.

## Local development

Developers run `uv run mip-notebook` (or `./run-local-llm-codex.sh`). The runner syncs `docs/user/` into `workspace/docs/`, sets `MIP_JUPYTER_ROOT` and JupyterLab `ServerApp.root_dir` to `workspace/` (production parity with `/home/jovyan/work`), and keeps agent docs / editable `python-client` on the repo via `MIP_AGENT_DOCS` and the uv environment.
