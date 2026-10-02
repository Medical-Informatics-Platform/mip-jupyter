# Agent Exploration

**Read when:** Multi-step exploration, catalog audit, or novel stroke analysis with Cohort Scout.

**Skip if:** Single small notebook edit (`04-jupyter-mcp.md` is enough).

Use `CODEX_REASONING_EFFORT=medium` for this workflow if the default is `low`.

Skip this page for a single small notebook tweak — use direct notebook tools
(`create-notebook` / `append-*` / `edit-cell`) per `04-jupyter-mcp.md`.

## Build notebook: ONE script, transfer once

Write the whole analysis as **ONE** `scratch/<name>.py` with `# %%` cell markers
(via `scratch-write-file`), validate with `python scratch/<name>.py`, then
`scratch-to-notebook` **once**. Never write per-cell fragment files.

| Choose | When |
|--------|------|
| **ONE script → transfer once (default)** | Full analysis: `scratch-write-file` ONE `scratch/<name>.py` (`# %%` markers) → `python scratch/<name>.py` (exit 0) → `scratch-to-notebook` → `open-file` / `notebook-outline` |
| **Direct cell tools** | Only a tiny tweak to an existing notebook (`append-code`/`edit-cell`/`run-cell`) |

## Turn 1 setup

1. `jupyter-mcp read-guide --page agent-exploration` (this page)
2. `jupyter-mcp scratch-list` — resume existing artifacts before creating new scripts

## Phased workflow

| Phase | Action |
|-------|--------|
| **A — Discovery** | `jupyter-mcp mip-env-status`, `mip-data-model-summary stroke --version 3.7`, SSR coverage (`recipes/stroke-analysis` step 3) |
| **B — Catalog audit** | `jupyter-mcp mip-algorithm-summary`, `jupyter-mcp read-guide --page 07-pipeline-algorithms`; signatures from `examples/algorithm_examples.py` |
| **C — Novel analysis** | `jupyter-mcp scratch-write-file scratch/<name>.py` — ONE script for one hypothesis, `# %%` markers, `scratch-replace-snippet` for fixes, **`python scratch/<name>.py`** until exit 0 |
| **D — Notebook** | `jupyter-mcp scratch-to-notebook`, `notebook-outline`, `open-file` |

Do **not** stop after Phase B metadata alone. Complete Phase C unless coverage fails.
Do **not** stop at a verified `.py` alone — finish Phase D unless the user asked for a script only.

## Resume after tool-call error

1. New chat → `scratch-list` → continue newest complete `scratch/<name>.py`
2. `scratch-write-file` (rewrite the script, max 8000 chars) or `scratch-replace-snippet` only

## Reference signatures

Use `workspace/examples/algorithm_examples.py` and `feres_analysis.ipynb` patterns.
Do not invent methods or sklearn-style `x=`/`y=` kwargs.

## Deliverables (session end)

1. Notebook transferred from scratch with `scratch-to-notebook` (the deliverable is
   the `.ipynb`, not the `.py`), plus the underlying `scratch/<name>.py`
2. Chat summary: primary OR (95% CI) if logistic run, next human fix

## Starter prompt (user paste)

```text
Exploration on Stroke 3.7 / SSR. Turn 1: scratch-list.
Phases A–D.
Novel work: copy from examples/algorithm_examples.py.
End with OR (95% CI) and next action.
```

**Next file:** [`recipes/stroke-analysis.md`](recipes/stroke-analysis.md) for novel inference rules.
