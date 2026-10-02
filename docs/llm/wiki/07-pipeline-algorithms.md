# Pipeline Algorithms — Catalog and Examples

**Read when:** Which algorithms exist, how to call them, or a minimal runnable example.

**Skip if:** Stroke inference rules alone are enough (`recipes/stroke-analysis.md`).

## Catalog

**30** typed `Pipeline` methods + **4** preprocessing builders. Registry:
`python-client/mip/catalog_registry.py` (`PIPELINE_BACKEND_ALGORITHMS`).

```python
pipeline.available_algorithms()
client.algorithms().list()
pipeline.recommend_algorithms()
```

Full runnable script: `workspace/examples/algorithm_examples.py`.

Preprocessing: `MissingValuesHandler`, `OutlierWinsorizer`,
`CategoricalColumnCreator`, `LongitudinalTransformer` (via `Pipeline(..., longitudinal=...)`).

Call typed methods directly — no `Pipeline.run()`. Default `mode="transient"`.

| Pipeline method | Backend | Purpose |
|-----------------|---------|---------|
| `describe()` | `describe` | Summary stats / coverage |
| `histogram(variable=..., bins=...)` | `histogram` | Binned counts |
| `t_test(...)` | `ttest_independent` | Two-group comparison |
| `one_sample_t_test(...)` | `ttest_onesample` | One-sample t-test |
| `paired_t_test(...)` | `ttest_paired` | Paired measurements |
| `chi_square_test(x=..., y=...)` | `chi_squared` | Categorical association |
| `fisher_exact(x=..., y=...)` | `fisher_exact` | 2×2 exact test |
| `pearson_correlation(x=..., y=...)` | `pearson_correlation` | Linear correlation |
| `quartiles(variable=...)` | `quartiles` | Quartile summary |
| `anova_oneway(...)` / `anova_twoway(...)` | `anova_*` | ANOVA |
| `mann_whitney_u_test(...)` | `binned_mann_whitney_u_test` | Non-parametric two-group |
| `outlier_report(...)` | `outlier_report` | Outlier bounds |
| `linear_regression(...)` / `_cv(...)` | `linear_regression*` | OLS |
| `logistic_regression(...)` / `_cv(...)` | `logistic_regression*` | Binary logistic |
| `cox_regression_classical(...)` / `_stacked(...)` | `cox_regression_*` | Cox PH |
| `lmm(...)` / `glmm_binary(...)` / `glmm_ordinal(...)` | `lmm` / `glmm_*` | Mixed models |
| `linear_svm(...)` | `linear_svm` | Linear SVM |
| `kmeans(...)` / `pca(...)` / `pca_with_transformation(...)` | `kmeans` / `pca*` | Clustering / PCA |
| `naive_bayes_gaussian(...)` / `_categorical(...)` (+ `_cv`) | `naive_bayes_*` | Naive Bayes |

Signatures: copy from `algorithm_examples.py`. Contributor registry updates:
`dev-contributor.md` + `test_catalog_registry.py`.

## Result keys (common)

| Algorithm | Highlights |
|-----------|------------|
| Describe | `featurewise[].data.num_dtps`, `.mean`, `.std` |
| Histogram | `bins`, `counts` |
| T-test | `t_stat`, **`p`**, `mean_diff`, `cohens_d` |
| Chi-square | `chi2`, **`p_value`**, `dof` |
| Logistic | `summary.coefficients` / `pvalues` / `lower_ci` / `upper_ci` |

Others: `summarize()` in `algorithm_examples.py`. Federated aggregates only; pass
**creators** in `new_columns`; filter enums often codes (`"0"`/`"1"`). Stroke:
check SSR coverage with `describe()` (`recipes/stroke-analysis` step 3) before
inference-heavy scripts.

**Next file:** `algorithm_examples.py` or `02-analysis-workflow.md`.
