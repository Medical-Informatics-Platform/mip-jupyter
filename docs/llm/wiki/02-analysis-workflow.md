# Analysis Workflow

**Read when:** Build or extend a federated analysis notebook.

**Skip if:** Env only (`05`) or MCP edits only (`04`).

## Pattern

```text
Connect → Discover → Select → Transform → Analyze
```

```python
import mip
from mip.filters import F
from mip.preprocessing import (
    CategoricalColumnCreator,
    MissingValuesHandler,
    OutlierWinsorizer,
)

client = mip.Client.from_env()
dm = client.catalog().data_model("Dementia")
dataset = dm.datasets["ADNI"]
age, mmse = dm.variables["Age"], dm.variables["MMSE"]

analysis_set = mip.AnalysisSet(
    data_model=dm, datasets=[dataset], variables=[age, mmse]
)
filters = (F(age) >= 50) & F(mmse).is_not_null()
missing = MissingValuesHandler(strategies={mmse: "mean"})
outliers = OutlierWinsorizer(
    strategies={mmse: "iqr"}, tails={mmse: "both"}, folds={mmse: 1.5}
)
creator = CategoricalColumnCreator(
    label="Cognitive profile",
    rules={"Preserved": F(mmse) >= 27, "Impaired": F(mmse) < 20},
    default_enumeration="Unclassified",
)
pipeline = mip.Pipeline(
    analysis_set=analysis_set,
    filters=filters,
    handle_missing=missing,
    outlier_handling=outliers,
    new_columns=[creator],
)
pipeline.describe()
pipeline.histogram(variable=mmse, bins=20)
```

Order is fixed: `AnalysisSet` → filters → missing → outliers → new_columns → algorithm.

Default run mode is transient; use persisted only when the user asks to keep the
experiment. Inspect with `result.summary()` / `result.raw` / `result.payload`.

## Pitfalls

- `Client.from_env()`, not `Client()`; bracket access for datasets/variables
- No `Pipeline.run()` — call typed algorithm methods
- `new_columns=[creator]`; algorithms use `creator.variable`
- Federated aggregates only — no raw row extraction

Algorithms + result keys: `07-pipeline-algorithms.md`. Stroke patterns:
`recipes/stroke-analysis.md`. Example: `workspace/examples/feres_analysis.ipynb`.

**Next file:** example notebook or `03-mip-client-api.md`.
