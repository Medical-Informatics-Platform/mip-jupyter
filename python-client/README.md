# MIP Python client

Notebook-facing library for MIP federated analysis via platform-backend experiments.

## Install

From the repository root, `uv sync --extra dev` installs this client editable.
Standalone:

```bash
python3 -m pip install -e .
```

Optional notebook extras:

```bash
python3 -m pip install -e ".[notebook]"
```

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

```bash
python3 -m unittest discover -s tests -p "test_*.py"
```
