# Onboarding — New MIP User

**Read when:** New to MIP or asking what to do first in a notebook.

**Skip if:** Client/infra edits — see `dev-contributor.md`.

## Goal

Connect → discover a data model → select datasets/variables → run a simple analysis.

```python
import mip
from mip.filters import F
from mip.preprocessing import MissingValuesHandler

client = mip.Client.from_env()
catalog = client.catalog()
dm = catalog.data_model("Dementia")
dm.summary(); dm.tree(include_variables=True)

adni = dm.datasets["ADNI"]
age, mmse = dm.variables["Age"], dm.variables["MMSE"]
# dm.variables.search("MMSE"); dm.help(); pipeline.recommend_algorithms()

pipeline = mip.Pipeline(
    analysis_set=mip.AnalysisSet(
        data_model=dm, datasets=[adni], variables=[age, mmse]
    ),
    filters=F(age) >= 50,
    handle_missing=MissingValuesHandler(strategies={mmse: "mean"}),
)
pipeline.histogram(variable=mmse, bins=20).summary()
```

`Client.from_env()` uses the portal-configured connection. Operator env details:
`05-env-and-backend.md` — do not quote env var names to end users unless they ask
about local setup. Goal → API guide: workspace `docs/how-to-choose.md`.

## Rules

- Use the `mip` client only — no direct execution-service calls
- No `.table()` API; select and show **labels** only

Runnable walkthrough: `workspace/Welcome.ipynb`. Next: that notebook, or
`02-analysis-workflow.md`.
