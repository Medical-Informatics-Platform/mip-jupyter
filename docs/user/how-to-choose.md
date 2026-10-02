# How to Choose the Right API Call

Use this guide when you have a MIP object and want to know what to call next. Every notebook-facing object also exposes `.help()` — for example `dm.help()` or `pipeline.help()`.

Selection and display use **human-readable labels** only (for example `"Age"`, `"ADNI"`, `"Dementia"`). Internal codes are never shown or typed in notebook code.

## Goal → API quick reference

| User goal | Use |
|-----------|-----|
| See available data models | `catalog.summaries()` or `catalog.tree()` |
| Pick a data model | `catalog.data_model("Dementia")` |
| Understand a data model | `dm.summary()` then `dm.tree()` (collapsible HTML in notebooks) |
| Find a variable | `dm.variables.search("age")` |
| See only numeric variables | `dm.variables.numerical()` |
| See only categorical variables | `dm.variables.categorical()` |
| Browse variables by group | `dm.variables.tree(group="Demographics")` |
| Understand a variable | `variable.summary()` then `variable.details()` |
| See allowed categories | `variable.categories()` |
| Check datasets | `dm.datasets.list()` or `dm.datasets.search("ADNI")` |
| Tabular preview of variables | `dm.variables.to_frame()` (includes `group_path`) |
| Tabular preview of datasets | `dm.datasets.to_frame()` |
| Find algorithms | `client.algorithms().search("logistic")` |
| Tabular preview of algorithms | `client.algorithms().to_frame()` |
| Preview analysis selection | `analysis_set.summary()` or `analysis_set.explain()` |
| Build selection quickly | `dm.select(datasets=["ADNI"], variables=["Age", "MMSE"])` |
| Preview the full request | `pipeline.explain()` |
| Get algorithm suggestions | `pipeline.recommend_algorithms()` |
| Understand results | `result.highlights()`, `result.to_frame()`, `result.summary()` |
| Plot results | `result.plot()` (histogram, describe, t-test, chi-square, pearson, logistic, …) |
| Interactive browse | `catalog.browse()` / `dm.browse()` (requires ipywidgets) |

## Typical exploration flow

```python
import mip

client = mip.Client.from_env()
catalog = client.catalog()

# 1. What data models can I use?
catalog.summaries()
catalog.tree()

# 2. Pick one and explore
dm = catalog.data_model("Dementia")
dm.help()
dm.summary()

# 3. Find variables and datasets
dm.variables.search("age")
dm.variables.to_frame().head()
dm.datasets.search("ADNI")

# 4. Inspect one variable
age = dm.variables["Age"]
age.summary()
age.categories()

# 5. Build and preview an analysis
adni = dm.datasets["ADNI"]
mmse = dm.variables["MMSE"]
analysis_set = mip.AnalysisSet(data_model=dm, datasets=[adni], variables=[age, mmse])
pipeline = mip.Pipeline(analysis_set=analysis_set)
pipeline.recommend_algorithms()
pipeline.explain()
```

## Tabular previews from search results

Search methods return lists. Convert any list of variables, datasets, or algorithms to a DataFrame:

```python
mip.to_frame(dm.variables.search("age"))
mip.to_frame(client.algorithms().search("logistic"))
```

## More help

- [Quickstart](quickstart.md) — connect and run a simple analysis
- [API reference](api-reference.md) — filters, preprocessing, pipeline methods
- `Welcome.ipynb` — guided walkthrough with runnable examples
