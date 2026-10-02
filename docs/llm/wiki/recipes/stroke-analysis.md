# Federated Stroke Analysis — Recipe

**Read when:** Federated stroke analysis, including novel / significance work.

**Skip if:** General onboarding only (`01-onboarding.md`).

Self-contained for stroke stats — do not chain `02`/`03`/`04` on startup.

## Novel analysis (default)

1. `jupyter-mcp read-guide --page recipes/stroke-analysis --topic novel`
2. `jupyter-mcp mip-data-model-summary stroke --version 3.7`
3. Confirm SSR coverage: `Pipeline(analysis_set=...).describe()` on SSR over `Admission score`, `24h score`, `3m mRS good outcome`, `Age`, `Sex`, `Clinical syndrome` — **stop** if any SSR row of `summary()["featurewise"]` has `num_dtps` 0 (often empty: `Known AF`, `Oral anticoagulation`, `Prestroke sleep hours`)
4. Pre-specify one primary hypothesis (outcome, predictors, SSR-only)
5. `jupyter-mcp scratch-write-file scratch/<name>.py` — the whole analysis, `# %%` cell markers, one arg per line (or `--content-file`)
6. Fix with `jupyter-mcp scratch-replace-snippet` (or rewrite the file); no per-cell fragments
7. `python scratch/<name>.py`; save CSVs under `scratch/`
8. `jupyter-mcp scratch-to-notebook` → `notebook-outline` → `open-file`
9. Primary report: **adjusted logistic OR (95% CI)**; secondary p-values exploratory

Patterns: `examples/feres_analysis.ipynb`, `examples/algorithm_examples.py`.

## Guardrails

- One primary outcome (often poor 3m mRS from `"3m mRS good outcome"`)
- Coverage must be confirmed — catalog presence ≠ SSR data
- Parenthesize filters: `(F(nihss) >= 10) & (F(nihss) < 20)`
- `dm.variables["Age"]` + `F(age_var)` — never `F("Age")` / `pipeline.get_variable()`
- `AnalysisSet` + `Pipeline(analysis_set=...)`; `MissingValuesHandler(strategies={...})`
- Parse logistic with `parse_logistic_regression_summary()` / `format_logistic_term()` from `dev.stroke_federated`
- Dataset: `datasets=[ssr]` only — never mix SSR with SSR-even/odd
- Often empty in SSR (exclude primary): `"Known AF"`, `"Oral anticoagulation"`,
  `"Prestroke sleep hours"`

```python
client = mip.Client.from_env()
dm = client.catalog().data_model("Stroke 3.7")
ssr = dm.datasets["SSR"]
pipeline = mip.Pipeline(
    analysis_set=mip.AnalysisSet(data_model=dm, datasets=[ssr], variables=selected),
    filters=common_filters,
    handle_missing=common_missing,
    new_columns=[poor_outcome_creator],
)
pipeline.logistic_regression(x=[age, nihss], y=poor_outcome, positive_class="Yes")
```

Result keys: t-test `p`; chi-square `p_value`; logistic `summary.coefficients` /
`pvalues` / `lower_ci` / `upper_ci`. Effect sizes + CIs over p alone; disclose
multiplicity. No `inputdata()` / `to_frame()` / sklearn on rows.

## Forbidden

Heredocs / `write_stdin` / shell file writes; `new_columns=[creator.variable]`;
ending with CSVs only — always transfer to `scratch/<name>.ipynb`.

**Next:** `scratch-write-file` the ONE analysis script once coverage is confirmed.
