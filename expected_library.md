# MIP Jupyter Expected Library

Contract for the notebook-side `mip` library built in `mip-jupyter` and consumed inside Jupyter/JupyterHub.

## Design Rules

- The Python library is a thin client over `platform-backend`.
- Notebook code calls `platform-backend` only, not Exaflow directly.
- Data model discovery comes from backend data-model DTOs.
- Algorithm execution defaults to `/experiments/transient`; persisted execution uses `/experiments`.
- Search/list APIs return native Python lists.
- No `.table()` API exists.


## MVP Compliance Review

| MVP item | Implementation status |
|----------|-----------------------|
| Thin client over platform-backend | Implemented through internal `Transport`; no direct Exaflow calls. |
| Public entry points | `mip.Client`, `mip.AnalysisSet`, `mip.Pipeline`. |
| Public DSL/builders | `mip.filters.F`, `mip.preprocessing.MissingValuesHandler`, `mip.preprocessing.OutlierWinsorizer`, `mip.preprocessing.CategoricalColumnCreator`. |
| Derived variables | `mip.derived.DerivedVariable` exposed via `CategoricalColumnCreator.variable`. |
| Catalog objects | `Catalog`, `DataModel`, `VariableCollection`, `DatasetCollection`, `Variable`, `Dataset`. |
| Native list search/list results | `Catalog` search methods and collection `.search()` / `.to_list()` return `list`. |
| No old table API | No `.table()` method; old `ResultTable` API is removed. |
| AnalysisSet scope | Holds only selected data model, datasets, and variables. |
| Fixed Pipeline flow | Selection -> filters -> missing handling -> outlier handling -> new_columns -> algorithm. |
| Experiment payload | `analysis: AnalysisRequestDTO` with ordered `preprocessing` array and `inputdata.variables`. |
| Algorithm methods | `describe`, `histogram`, `t_test`, `pearson_correlation`, `chi_square_test`, `logistic_regression`. |
| Execution endpoints | `mode="transient"` posts `/experiments/transient`; `mode="persisted"` posts `/experiments`. |
| Preprocessing shape | Ordered preprocessing steps; strategy dictionaries keyed by variable code. |
| Results | `Result` and `ModelResult` expose `summary()`, `raw`, and `payload`; no enrichment APIs. |
| sklearn export | Implemented in `mip.sklearn` and exposed via `ModelResult.to_sklearn()`. |

## Module Layout

```text
mip/
  __init__.py
  client.py
  catalog.py
  datamodel.py
  variables.py
  datasets.py
  filters.py
  preprocessing.py
  derived.py
  request_builder.py
  analysis.py
  pipeline.py
  algorithms.py
  results.py
  sklearn.py
  transport.py
  metadata_tree.py
  display.py
  labels.py
  exceptions.py
```

`workspace/Welcome.ipynb` is the runnable companion to this contract.

## Public API

```python
import mip
from mip.filters import F
from mip.preprocessing import CategoricalColumnCreator, MissingValuesHandler, OutlierWinsorizer

client = mip.Client.from_env()
catalog = client.catalog()
algorithms = client.algorithms()
experiments = client.experiments()
```

Runnable companion notebook: `workspace/Welcome.ipynb`.

`Client.from_env()` reads:

```text
PLATFORM_BACKEND_URL or MIP_BASE_URL
PLATFORM_TOKEN or MIP_TOKEN
PLATFORM_BACKEND_TIMEOUT
PLATFORM_BACKEND_ALLOW_REDIRECTS
```

## Catalog Discovery

Public selection uses **labels** (human-readable names). Internal codes are kept private and used only when building backend payloads.

```python
catalog.list()
catalog.summaries()
catalog.tree()

dm = catalog.data_model("Dementia")
dm.summary()
dm.list_datasets()
dm.datasets.list()
dm.list_groups()
dm.tree(include_variables=True)
dm.tree(group="Clinical", include_variables=True)
dm.variables.tree(group="Cognitive")
dm.variables.list()
dm.variables.search("MMSE")
dm.datasets.search("ADNI")

age = dm.variables["Age"]
adni = dm.datasets["ADNI"]
age.details()
age.categories()  # e.g. ["Male", "Female"] not backend codes
```

## Discoverability

Notebook-facing objects expose `.help()` with useful methods and typical next steps. `.help()` returns a `HelpText` object with notebook-friendly `_repr_html_()` (no duplicate print + return output).

```python
client.help()
catalog.help()
dm.help()
age.help()
pipeline.help()
```

Evaluating objects in a notebook cell renders a compact HTML card via `_repr_html_()` for `DataModel`, `Dataset`, `Variable`, `AnalysisSet`, `Pipeline`, and `Result`.

`catalog.tree()`, `dm.tree()`, and `dm.variables.tree()` return a `MetadataTree`: notebooks show a collapsible HTML tree; `str(tree)` keeps the ASCII form for copy/paste and agents.

Tabular previews:

```python
dm.variables.to_frame()  # label, type, group_path, description, n_categories, …
dm.datasets.to_frame()
client.algorithms().to_frame()
mip.to_frame(dm.variables.search("age"))
```

Pipeline guidance:

```python
pipeline.available_algorithms()
pipeline.recommend_algorithms()
```

User-facing decision guide: `docs/user/how-to-choose.md` (shipped to workspace `docs/`).

## Analysis Set

```python
analysis_set = mip.AnalysisSet(
    data_model=dm,
    datasets=[adni],
    variables=[age, mmse],
)

# Shorthand from a data model (labels or objects):
analysis_set = dm.select(datasets=["ADNI"], variables=["Age", "MMSE"])

analysis_set.summary()
analysis_set.explain()
analysis_set.histogram(variable=mmse, bins=20)
```

`AnalysisSet` only represents selected data model, datasets, and variables.

## Filters

```python
expr = (F(age) >= 50) & F(mmse).is_not_null()
expr.explain()
```

Supported operators and helpers:

```python
F(age) == 50
F(age) != 50
F(age) > 50
F(age) >= 50
F(age) < 80
F(age) <= 80
F(mmse).is_null()
F(mmse).is_not_null()
F(diagnosis).isin(["AD", "CN"])
F(diagnosis).not_in(["AD", "CN"])
F(mmse).between(20, 26)
F(mmse).not_between(20, 26)
expr1 & expr2
expr1 | expr2
~expr
```

`F.contains()`, `F.starts_with()`, and `F.ends_with()` serialize to the same operator names, but Exaflow currently accepts only the operators listed in its filter validator (`between`/`not_between` are supported; string-match operators are not yet).

`~expr` rewrites to Exaflow-supported operators (for example `~F(x).isin([...])` becomes `not_in`). Exaflow accepts only `AND` and `OR` group conditions.

## Preprocessing

```python
missing = MissingValuesHandler(
    strategies={age: "median", mmse: "mean"},
)

outliers = OutlierWinsorizer(
    strategies={mmse: "iqr"},
    tails={mmse: "both"},
    folds={mmse: 1.5},
)
```

Variable-object keys in preprocessing maps serialize to internal codes automatically; pass `Variable` or `DerivedVariable` objects, not string codes.

`CategoricalColumnCreator` builds a derived categorical column from filter rules:

```python
creator = CategoricalColumnCreator(
    label="Cognitive profile",
    rules={
        "Preserved": (F(mmse) >= 27) & (F(cdr) == 0),
        "Severe impairment": F(mmse) < 20,
    },
    default_enumeration="Unclassified",
)

derived = creator.variable
derived.label
derived.categories()
derived.details()
```

The creator serializes to the `categorical_column_creator` preprocessing step with `strategy="filter_rules"`. Internal `_code` is generated from the label for backend payloads only.

## Pipeline Execution

```python
pipeline = mip.Pipeline(
    analysis_set=analysis_set,
    filters=(F(age) >= 50) & F(mmse).is_not_null(),
    handle_missing=missing,
    outlier_handling=outliers,
    new_columns=[creator],
)

pipeline.describe()
pipeline.histogram(variable=mmse, bins=20)
pipeline.t_test(variable=mmse, group_by=diagnosis, group_a="AD", group_b="CN")
pipeline.pearson_correlation(x=mmse, y=cdr)
pipeline.chi_square_test(x=sex, y=diagnosis)
logreg = pipeline.logistic_regression(
    x=[age, sex, mmse, cdr, apoe4],
    y=diagnosis,
    positive_class="AD",
)
```

Execution order is fixed:

```text
AnalysisSet selection -> filters -> handle_missing -> outlier_handling -> new_columns -> algorithm
```

Experiment requests use:

```python
{
  "name": "...",
  "analysis": {
    "inputdata": {
      "data_model": "...",
      "datasets": ["..."],
      "validation_datasets": null,
      "filters": {...},
      "variables": ["..."],  # raw source variables only
    },
    "preprocessing": [
      {"name": "missing_values_handler", "parameters": {...}},
      {"name": "categorical_column_creator", "parameters": {...}},
    ],
    "algorithm": {
      "name": "...",
      "x": ["..."],
      "y": ["..."],
      "parameters": {...},
    },
  },
}
```


## Algorithm Registry

```python
registry = client.algorithms()
registry.list()
registry.search("logistic")
registry.preprocessing()
registry.statistics()
registry.models()
```

Each returned `Algorithm` exposes `.spec()` for the backend DTO and `.summary()` for a compact readable view (`label`, `description`, `type` only).

## Label-only public API (breaking changes)

- Public identity is **label**, not internal code.
- `Variable.metadata()` replaced by label-safe `Variable.details()`.
- `Algorithm.summary()` no longer includes backend `name`.
- `Catalog.data_model()`, `VariableCollection.__getitem__`, and `DatasetCollection.__getitem__` index by label (case-insensitive).
- `categories()` returns human-readable enumeration labels.
- Filter `isin([...])` accepts enumeration labels; codes are mapped during payload serialization.
- `CategoricalColumnCreator(label=...)` replaces the `code=` parameter; internal code is derived automatically.

## Experiment Registry

```python
experiments = client.experiments()
experiments.list()
experiments.get("experiment-id")
experiments.delete("experiment-id")
```

The experiment registry is for persisted experiment management. Pipeline execution remains the primary analysis API.

## Experiment Modes

All `AnalysisSet` and `Pipeline` execution methods default to transient execution:

```python
pipeline.histogram(variable=mmse)                  # POST /experiments/transient
pipeline.histogram(variable=mmse, mode="persisted") # POST /experiments
```

## Results

```python
result.summary()
result.raw
result.payload
```

Evaluating a `Result` shows algorithm-aware highlights and a tabular preview when
available. Common helpers:

```python
result.highlights()
result.to_frame()
result.plot()  # histogram, describe, t-test, chi-square, pearson, logistic, …
```

`catalog.browse()` / `dm.browse()` provide an optional ipywidgets picker (install
the notebook extra). A full JupyterLab side-panel extension is not shipped; the
widget browser covers interactive selection in notebooks.

Histogram and other supported results may use `.plot()`. Unsupported plotting or
tabular previews raise `UnsupportedOperationError`.

Logistic regression results expose:

```python
logreg.feature_schema()
sklearn_model = logreg.to_sklearn()
sklearn_model.feature_names_in_
sklearn_model.predict(X_preprocessed)
sklearn_model.predict_proba(X_preprocessed)
```

Local prediction requires a user-preprocessed pandas DataFrame whose columns match `sklearn_model.feature_names_in_` exactly.
