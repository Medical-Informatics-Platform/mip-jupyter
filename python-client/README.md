# mip-client

Python client for MIP federated analysis via platform-backend experiments.
The distribution is `mip-client`; the import name is `mip`.

This directory is a self-contained package: it never imports or reads files
from the rest of mip-jupyter, so it can be released (and later moved) on its
own. Tests that check the notebook workspace live in `dev/`.

## Install

```bash
python3 -m pip install "mip-client[notebook]==<version>"
```

`<version>` is a mip-jupyter release tag; every release publishes the client to
[PyPI](https://pypi.org/project/mip-client/) at that version. Releases without a
PyPI upload (0.2.1 and earlier) install from the tag:
`python3 -m pip install "mip-client[notebook] @ git+https://github.com/Medical-Informatics-Platform/mip-jupyter@<version>#subdirectory=python-client"`.
Drop `[notebook]` outside Jupyter.

For development, `uv sync --extra dev` at the repository root installs this
client editable. To work on the client alone, from this directory:

```bash
uv sync --extra dev --extra notebook
```

## Configure

`mip.Client.from_env()` reads `PLATFORM_BACKEND_URL` (for example
`https://<host>/services`) and `MIP_TOKEN`.

From your own computer, set `MIP_URL=https://<host>` and `MIP_API_TOKEN` to a
JupyterHub API token with the `custom:mip-platform-token` permission, created at
`https://<host>/notebook/hub/token`. See
[Use MIP from your own computer](https://github.com/Medical-Informatics-Platform/mip-jupyter/blob/master/docs/user/remote-access.md).

## `mip` command for AI assistants

`mip guide`, `mip env-status`, `mip catalog`, `mip data-model LABEL`,
`mip search-variables LABEL TEXT` and `mip algorithms` print compact JSON for AI
assistants. `mip agent init` writes an `AGENTS.md` that routes an assistant to
them. The guide pages ship in `mip/agent_docs/`; the code is in `mip/agent.py` and
`mip/cli.py`.

## API overview

| Object | Purpose |
|--------|---------|
| `Client` | Owns backend transport and creates catalog/algorithm/experiment facades |
| `ExperimentRegistry` | Lists, reads, and deletes persisted experiments |
| `Catalog` | Discovers data models, variables, and datasets |
| `AnalysisSet` | Holds selected data model, datasets, and variables |
| `Pipeline` | Applies filters/preprocessing and executes named algorithms |
| `F` | Builds backend-compatible filter expressions |
| `MissingValuesHandler`, `OutlierWinsorizer` | Build preprocessing payloads |
| `KMeansClusterCreator` | Reuse a K-means result as a categorical cluster column; clustering variables with missing values are dropped |
| `Result`, `ModelResult` | Wrap raw backend results and logistic-regression sklearn export |
| `mip.sklearn` | Builds sklearn estimators from supported backend model output |

### Reuse K-means clusters as a column

```python
clusters = pipeline.kmeans(features=[lefthippocampus, righthippocampus], k=3)
creator = KMeansClusterCreator(label="Cluster", source=clusters)
with_clusters = Pipeline(analysis_set=analysis_set, new_columns=[creator])
with_clusters.chi_square_test(x=creator.variable, y=diagnosis)
```

The pipeline that uses the column must have the same data model, datasets, and
filters as the K-means run; otherwise the engine rejects the request.

## Removed old API

The MVP is a strict replacement. Legacy notebook APIs such as `configure`, `Context`, namespace `Analysis`, and `ResultTable` are no longer part of this package.

## Test

From this directory:

```bash
uv run pytest -q
uv run python verify_script.py
```

- Tests use `unittest` + `unittest.mock`, patching `requests.Session`; no live HTTP.
- Add a regression test with every behavior fix.
- When the public API changes, update [expected_library.md](expected_library.md),
  `docs/user/api-reference.md`, and `python-client/mip/agent_docs/wiki/03-mip-client-api.md` together.

## Release

The client ships with every mip-jupyter release, at the release's version.

1. Before the release, set `version` in `pyproject.toml` to the release tag
   (for example `0.3.0`), then run `uv lock` at the repository root, and commit.
2. Publish the GitHub release. The release workflow fails if the tag and
   `version` disagree, and otherwise publishes the wheel and sdist to PyPI with
   trusted publishing (no token). Pre-releases ship images only.
