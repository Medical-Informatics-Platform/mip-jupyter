# Repository layout

```text
mip-jupyter/
  README.md
  AGENTS.md                 # Agent bootstrap (Cursor, Codex in IDE)

  docker/
    singleuser/
      Dockerfile            # Production single-user Jupyter image
      entrypoint.sh
    hub/
      Dockerfile            # JupyterHub image
      jupyterhub_config.py

  python-client/            # mip-client package (import `mip`), self-contained
    mip/                    # Installed as package in production images
      agent_docs/           # Agent wiki, shipped in the wheel and to /opt/mip-agent-docs/
    tests/
    expected_library.md     # API contract for client development
    pyproject.toml

  workspace/                # Notebooks seeded into /home/jovyan/work
    Welcome.ipynb           # Default landing / onboarding
    # examples/ is not in the repo: the examples live in mip-examples, mounted
    # read-only by MIP clusters. A local checkout there is git-ignored.
    # scratch/ is not in the repo: the entrypoint creates it empty in the
    # workspace and nothing is shipped into it.

  docs/
    user/                   # Canonical user docs → copied to workspace/docs/ in image
      README.md
      quickstart.md
      api-reference.md
      troubleshooting.md
      workspace-guide.md
    architecture.md
    repository-layout.md
    release-process.md
    operators.md

  dev/          # Local dev runner (not in production workspace)
```

## What production users see

```text
/home/jovyan/work/
  Welcome.ipynb             # Opens by default
  examples/                 # read-only link, when the cluster mounts the shared examples
  docs/                     # from docs/user/
  scratch/
```

## What production users do not see

- `python-client/` source tree
- Dockerfiles and Hub configuration
- `python-client/mip/agent_docs/` agent wiki (`/opt/mip-agent-docs/`)
- `dev/` tooling
- Repository CI files

## Deployment

Orchestration and environment configuration: **`mip/deployment`**. See [`operators.md`](operators.md).

## Legacy root paths

Root-level `Dockerfile.jupyter` and `Dockerfile.jupyterhub` were moved to `docker/singleuser/` and `docker/hub/`. Update build scripts and CI to use the new paths.
