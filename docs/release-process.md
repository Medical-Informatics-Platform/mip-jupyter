# Release process

## Versioning

- `python-client/` (`mip-client` package, import `mip`) is released with every release, at the release's version: set `version` in `python-client/pyproject.toml` to the release tag and run `uv lock` before publishing (see `python-client/README.md`). Pre-releases ship images only.
- Container images are tagged separately (for example `hbpmip/mip-jupyter:dev`).

## Build checklist

1. Run client tests: `python3 -m pytest python-client/tests -q`
2. Build single-user image: `docker build -f docker/singleuser/Dockerfile -t mip-jupyter:<tag> .`
3. Build Hub image: `docker build -f docker/hub/Dockerfile -t mip-jupyterhub:<tag> .`
4. Build notebook operator image: `docker build -t mip-notebook-operator:<tag> operator` (see [notebook-operator.md](notebook-operator.md)); bump the CRDs in `mip-infra-staging` with it.
5. Smoke-test the single-user container:
   - Jupyter opens at `/home/jovyan/work`
   - `Welcome.ipynb`, `docs/`, and `scratch/` are visible; `examples/` is visible
     when the cluster mounts the shared examples (`scripts/smoke-singleuser-image.sh`
     mounts a fixture)
   - `docs/` contains user guides from `docs/user/` (quickstart, api-reference, troubleshooting)
   - `docs/llm/` is **not** in the file browser
   - `import mip` succeeds in a notebook
   - `python-client/` and Dockerfiles are not in the file browser
6. Verify agent docs in image (operator):
   - `ls /opt/mip-agent-docs/llm/wiki/` includes `00-agent-workspace.md`
   - `agent_read_guide` MCP tool returns content
7. Hub integration smoke (in `mip/deployment`):
   - User login → `Welcome.ipynb` → `Client.from_env()` succeeds
   - Platform token refresh works when configured

## CI

GitHub Actions workflows in `.github/workflows/`:

- `ci.yml`: unit tests, operator tests and Docker builds on push and pull requests.
- `sast.yml`, `sca.yml`, `container-scan.yml`, `secrets-scan.yml`: security gates on pull requests (see [ci/README.md](../ci/README.md)).
- `ebrains.yml`: mirrors `master` and tags to EBRAINS GitLab.

## Publishing

Publishing a GitHub release runs `release-client.yml`, which publishes the `mip-client` wheel and sdist to [PyPI](https://pypi.org/project/mip-client/) (releases are immutable, so assets cannot be attached after publishing), and `publish_images.yml`, which builds and pushes all three images, tagged with the release tag, to Docker Hub and EBRAINS Harbor:

- `hbpmip/mip-jupyter` (single-user)
- `hbpmip/mip-jupyterhub` (Hub)
- `hbpmip/mip-notebook-operator`

Harbor copies live under `docker-registry.ebrains.eu/medical-informatics-platform/`. Required repository secrets: `DOCKER_USERNAME`, `DOCKER_PASSWORD`, `HARBOR_USERNAME`, `HARBOR_PASSWORD`. PyPI needs no secret: the `mip-client` project on pypi.org has a trusted publisher for this repository, workflow `release-client.yml`, environment `pypi`. Update `docker/hub/jupyterhub_config.py` image references when rolling out a new single-user tag.
