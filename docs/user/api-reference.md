# MIP Python Client — API Reference

The `mip` client runs federated analyses on the MIP platform. Use **labels** in notebook code; internal codes are handled automatically.

## Imports

```python
import mip
from mip.filters import F
from mip.preprocessing import CategoricalColumnCreator, MissingValuesHandler, OutlierWinsorizer
```

## Client and catalog

```python
client = mip.Client.from_env()
catalog = client.catalog()
dm = catalog.data_model("Dementia", version="0.1")  # version optional
dm.datasets["ADNI"]
dm.variables["Age"]
dm.variables.search("MMSE")
```

## Discoverability

Every notebook object exposes `.help()` — for example `dm.help()` or `pipeline.help()`. See [How to choose the right API call](how-to-choose.md) for a goal → method guide.

```python
dm.help()
dm.variables.to_frame()  # includes group_path, description, n_categories
dm.datasets.to_frame()
mip.to_frame(dm.variables.search("age"))
pipeline.recommend_algorithms()
pipeline.available_algorithms()
dm.tree()  # collapsible HTML; str(dm.tree()) for ASCII
```

Evaluating `DataModel`, `Dataset`, `Variable`, `AnalysisSet`, `Pipeline`, or `Result` in a cell shows a compact HTML summary card. `dm.tree()` / `catalog.tree()` render collapsible HTML in notebooks.

## Filters

```python
(F(age) >= 50) & F(mmse).is_not_null()
F(diagnosis).isin(["Alzheimer's disease", "Cognitive normal"])  # enumeration labels
F(mmse).between(20, 26)
expr1 | expr2
~F(x).isin([...])  # rewrites to not_in
```

String-match operators (`contains`, `starts_with`, `ends_with`) may not be available for every variable type.

## Preprocessing

```python
MissingValuesHandler(strategies={age: "median", mmse: "mean"})
OutlierWinsorizer(strategies={mmse: "iqr"}, tails={mmse: "both"}, folds={mmse: 1.5})
CategoricalColumnCreator(label="Cognitive profile", rules={...}, default_enumeration="Other")
```

Use `creator.variable` for the derived column in downstream algorithms.

## Pipeline algorithms

**30** typed methods. See [Pipeline algorithms (agent wiki)](../llm/wiki/07-pipeline-algorithms.md) or run `workspace/examples/algorithm_examples.py`.

```python
pipeline.available_algorithms()
pipeline.histogram(variable=mmse, bins=20)
pipeline.logistic_regression(x=[age, sex], y=diagnosis, positive_class="Alzheimer's disease")
```

## Results

```python
result.highlights()
result.to_frame()
result.summary()
result.raw
result.payload
result.plot()  # histogram, describe, tests, pearson, logistic OR forest, …
logreg.to_sklearn()  # logistic regression only
```

Interactive catalog browse (optional `ipywidgets`):

```python
catalog.browse()
dm.browse()
```

## Registries

```python
client.algorithms().list()
client.algorithms().search("logistic")
client.experiments().list()
```
