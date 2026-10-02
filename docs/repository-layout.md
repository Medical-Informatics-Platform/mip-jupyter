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

  python-client/
    mip/                    # Installed as package in production images
    tests/
    pyproject.toml

  workspace/                # Notebooks seeded into /home/jovyan/work
    Welcome.ipynb           # Default landing / onboarding
    examples/
      feres_analysis.ipynb
      ist_scenario_1_aspirin.ipynb     # IST teaching scenarios (IST data model)
      ist_scenario_2_heparin.ipynb
      ist_scenario_3_prognosis.ipynb
    # scratch/ is not in the repo: the entrypoint creates it empty in the
    # workspace and nothing is shipped into it.

  docs/
    user/                   # Canonical user docs → copied to workspace/docs/ in image
      README.md
      quickstart.md
      api-reference.md
      troubleshooting.md
      workspace-guide.md
    llm/                    # Agent wiki (shipped to /opt/mip-agent-docs/, not user-visible)
    architecture.md
    repository-layout.md
    release-process.md
    operators.md

  dev/          # Local dev runner (not in production workspace)
  expected_library.md       # API contract for client development
```

## What production users see

```text
/home/jovyan/work/
  Welcome.ipynb             # Opens by default
  examples/
  docs/                     # from docs/user/
  scratch/
```

## What production users do not see

- `python-client/` source tree
- Dockerfiles and Hub configuration
- `docs/llm/` agent wiki (`/opt/mip-agent-docs/`)
- `dev/` tooling
- Repository CI files

## Deployment

Orchestration and environment configuration: **`mip/deployment`**. See [`operators.md`](operators.md).

## Legacy root paths

Root-level `Dockerfile.jupyter` and `Dockerfile.jupyterhub` were moved to `docker/singleuser/` and `docker/hub/`. Update build scripts and CI to use the new paths.
