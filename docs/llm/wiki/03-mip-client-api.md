# MIP Client API Cheat Sheet

**Read when:** API syntax for filters, preprocessing, pipeline, or results.

**Skip if:** `01` / `02` already covers it. Read [expected_library.md](../../../expected_library.md)
only when this page is insufficient.

## Rules

Thin client over the MIP platform backend. Entry points: `Client`, `AnalysisSet`,
`Pipeline`. Public identity is **label**. No `.table()` API.

```python
import mip
from mip.filters import F
from mip.preprocessing import CategoricalColumnCreator, MissingValuesHandler, OutlierWinsorizer

client = mip.Client.from_env()
dm = client.catalog().data_model("Dementia", version="0.1")  # version optional
dm.datasets["ADNI"]; dm.variables["Age"]; dm.variables.search("MMSE")
dm.select(datasets=["ADNI"], variables=["Age", "MMSE"])
dm.help(); pipeline.help(); pipeline.recommend_algorithms()
variable.details(); variable.categories()
dm.tree()  # collapsible HTML in notebooks; str(...) for ASCII
dm.variables.to_frame()  # includes group_path / n_categories
```

## Filters and preprocessing

```python
(F(age) >= 50) & F(mmse).is_not_null()
F(diagnosis).isin(["Alzheimer's disease", "CN"])  # labels; codes often "1"/"0" in filters
F(mmse).between(20, 26); expr1 | expr2; ~F(x).isin([...])

MissingValuesHandler(strategies={age: "median", mmse: "mean"})
OutlierWinsorizer(strategies={mmse: "iqr"}, tails={mmse: "both"}, folds={mmse: 1.5})
CategoricalColumnCreator(label="Cognitive profile", rules={...}, default_enumeration="Other")
```

String-match ops (`contains` / `starts_with` / `ends_with`) may fail validation.
Use `creator.variable` downstream.

## Pipeline

**30** typed methods — full catalog in `07-pipeline-algorithms.md`; smoke test
`workspace/examples/algorithm_examples.py`.

```python
pipeline = mip.Pipeline(analysis_set=..., filters=..., handle_missing=..., new_columns=[creator])
pipeline.available_algorithms(); pipeline.histogram(variable=mmse, bins=20)
pipeline.logistic_regression(x=[age, sex], y=diagnosis, positive_class="AD")
```

No `Pipeline.run()`. `new_columns` takes creators. Registries:
`client.algorithms().list()` / `.search(...)`; `client.experiments().list()`.
`Algorithm.summary()` → `{label, description, type}` only.

## Results

```python
result.highlights(); result.to_frame(); result.summary(); result.raw; result.payload
# plots: result.plot() for histogram/describe/tests/pearson/logistic
# logistic only: result.to_sklearn(), result.feature_schema()
# optional UI: catalog.browse() / dm.browse() (ipywidgets)
```

Common `summary()` keys: describe → `featurewise[].data.*`; histogram →
`bins`/`counts`; t-test → `p` (not `p_value`); chi-square → `p_value`; logistic →
`summary.coefficients` / `pvalues` / `lower_ci` / `upper_ci`. Full shapes: `07`.

**Next file:** `python-client/mip/` only when fixing client behavior.
