"""
MIP Pipeline — full stack examples (30 algorithms + preprocessing).

Run from the Jupyter workspace root:
  python examples/algorithm_examples.py

Uses Stroke 3.7 / SSR with federated calls only. Each section tries the typed
Pipeline wrapper and prints a compact summary. Steps that need variables or
cohorts SSR does not support are skipped with the platform error message.

Requires Client.from_env() (portal launch or PLATFORM_BACKEND_URL + MIP_TOKEN).
"""

# %% [markdown]
# # Full Pipeline stack examples
#
# Statistics, models, ML, and preprocessing builders on Stroke 3.7 / SSR.

# %%
from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import mip
from mip.filters import F
from mip.preprocessing import CategoricalColumnCreator, MissingValuesHandler, OutlierWinsorizer

DATA_MODEL = "Stroke 3.7"
DATASET = "SSR"


def print_header(title: str) -> None:
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def compact(value: Any, *, limit: int = 240) -> str:
    text = json.dumps(value, default=str)
    if len(text) > limit:
        return text[: limit - 3] + "..."
    return text


def summarize(method: str, raw: Any) -> str:
    if not isinstance(raw, dict):
        return compact(raw)

    if method == "describe":
        rows = raw.get("featurewise") or []
        parts = []
        for row in rows[:4]:
            if row.get("dataset") != DATASET:
                continue
            data = row.get("data") or {}
            parts.append(f"{row.get('variable')}: N={data.get('num_dtps')} mean={data.get('mean')}")
        return "; ".join(parts) or compact(raw)

    if method == "histogram":
        item = (raw.get("histogram") or [{}])[0]
        return f"bins={len(item.get('bins') or [])} counts_head={compact((item.get('counts') or [])[:5])}"

    if method in {"t_test", "one_sample_t_test", "paired_t_test", "mann_whitney_u_test"}:
        return f"t={raw.get('t_stat')} p={raw.get('p')} d={raw.get('cohens_d')}"

    if method in {"chi_square_test", "fisher_exact"}:
        return f"stat={raw.get('chi2') or raw.get('odds_ratio')} p={raw.get('p_value')}"

    if method == "pearson_correlation":
        return compact({k: raw.get(k) for k in ("title", "n_obs", "correlations") if k in raw})

    if method == "quartiles":
        return compact(raw.get("quantiles") or raw)

    if method.startswith("anova"):
        return compact(raw.get("anova_table") or raw.get("terms") or raw)

    if method == "outlier_report":
        rows = raw.get("featurewise") or []
        return compact([row.get("variable") for row in rows[:5]])

    if method in {"linear_regression", "linear_regression_cv"}:
        return f"N={raw.get('n_obs')} coeffs_head={compact((raw.get('coefficients') or [])[:4])}"

    if method in {"logistic_regression", "logistic_regression_cv"}:
        summary = raw.get("summary") or raw
        if isinstance(summary, dict) and "coefficients" in summary:
            return f"N={summary.get('n_obs')} coeffs_head={compact(summary.get('coefficients')[:4])}"
        return compact(summary)

    if method.startswith("cox_regression"):
        summary = (raw.get("summary") or raw) if isinstance(raw, dict) else raw
        return compact(summary)

    if method in {"lmm", "glmm_binary", "glmm_ordinal"}:
        return f"N={raw.get('n_obs')} converged={raw.get('converged')}"

    if method == "linear_svm":
        return f"N={raw.get('n_obs')} intercept={raw.get('intercept')}"

    if method == "kmeans":
        return f"N={raw.get('n_obs')} centers={compact(raw.get('centers'))}"

    if method.startswith("pca"):
        return f"N={raw.get('n_obs')} eigenvalues_head={compact((raw.get('eigenvalues') or [])[:4])}"

    if method.startswith("naive_bayes"):
        if "confusion_matrix" in raw:
            return compact(raw.get("confusion_matrix"))
        return f"classes={compact(raw.get('classes'))}"

    return compact(raw)


def run_step(method: str, runner: Callable[[], Any]) -> None:
    print_header(method)
    try:
        result = runner()
        payload = result.summary() if hasattr(result, "summary") else result
        print(f"  ok: {summarize(method, payload)}")
    except Exception as exc:  # noqa: BLE001 — surface platform rejections per algorithm
        print(f"  skipped: {exc}")


# %%
def build_context(client: mip.Client) -> dict[str, Any]:
    dm = client.catalog().data_model(DATA_MODEL)
    ssr = dm.datasets[DATASET]

    age = dm.variables["Age"]
    sex = dm.variables["Sex"]
    nihss_adm = dm.variables["Admission score"]
    nihss_24h = dm.variables["24h score"]
    ivt = dm.variables["IVT"]
    evt = dm.variables["EVT"]
    mrs_good = dm.variables["3m mRS good outcome"]

    poor = CategoricalColumnCreator(
        label="Poor outcome at 3 months",
        rules={"Yes": F(mrs_good) == "0"},
        default_enumeration="No",
    )
    acs_pcs = CategoricalColumnCreator(
        label="ACS vs PCS territory",
        rules={
            "ACS": F(dm.variables["Clinical syndrome"]).isin(["1", "2"]),
            "PCS": F(dm.variables["Clinical syndrome"]) == "4",
        },
        default_enumeration="Other",
    )

    filters = (
        F(age).is_not_null()
        & F(nihss_adm).is_not_null()
        & F(nihss_24h).is_not_null()
        & F(mrs_good).isin(["0", "1"])
        & F(sex).is_not_null()
    )

    analysis_set = mip.AnalysisSet(
        data_model=dm,
        datasets=[ssr],
        variables=[
            age,
            sex,
            nihss_adm,
            nihss_24h,
            ivt,
            evt,
            mrs_good,
            dm.variables["Clinical syndrome"],
        ],
    )

    pipeline = mip.Pipeline(
        analysis_set=analysis_set,
        filters=filters,
        handle_missing=MissingValuesHandler(
            strategies={
                age: "median",
                nihss_adm: "median",
                nihss_24h: "median",
            }
        ),
        outlier_handling=OutlierWinsorizer(
            strategies={nihss_adm: "iqr", nihss_24h: "iqr"},
            tails={nihss_adm: "both", nihss_24h: "both"},
        ),
        new_columns=[poor, acs_pcs],
    )

    return {
        "client": client,
        "dm": dm,
        "pipeline": pipeline,
        "age": age,
        "sex": sex,
        "nihss_adm": nihss_adm,
        "nihss_24h": nihss_24h,
        "ivt": ivt,
        "evt": evt,
        "poor": poor,
        "acs_pcs": acs_pcs,
    }


# %%
def show_preprocessing_stack(ctx: dict[str, Any]) -> None:
    print_header("Preprocessing stack")
    summary = ctx["pipeline"].summary()
    for step in summary.get("preprocessing") or []:
        print(f"  - {step.get('name')}: {compact(step, limit=120)}")
    print()
    print("  LongitudinalTransformer (longitudinal cohorts only; not run on SSR):")
    print(
        "  LongitudinalTransformer(visit1='BL', visit2='FL1', "
        "strategies={age: 'diff', mmse: 'second'})"
    )


# %%
def run_statistics(ctx: dict[str, Any]) -> None:
    p = ctx["pipeline"]
    age = ctx["age"]
    sex = ctx["sex"]
    nihss_adm = ctx["nihss_adm"]
    nihss_24h = ctx["nihss_24h"]
    ivt = ctx["ivt"]
    evt = ctx["evt"]
    poor = ctx["poor"]
    acs_pcs = ctx["acs_pcs"]

    run_step("describe", lambda: p.describe())
    run_step("histogram", lambda: p.histogram(variable=nihss_adm, bins=10))
    run_step(
        "t_test",
        lambda: p.t_test(
            variable=nihss_adm,
            group_by=poor.variable,
            group_a="Yes",
            group_b="No",
        ),
    )
    run_step("one_sample_t_test", lambda: p.one_sample_t_test(variable=age, mu=70.0))
    run_step(
        "paired_t_test",
        lambda: p.paired_t_test(measurement_1=nihss_adm, measurement_2=nihss_24h),
    )
    run_step("chi_square_test", lambda: p.chi_square_test(x=sex, y=poor.variable))
    run_step("fisher_exact", lambda: p.fisher_exact(x=ivt, y=evt))
    run_step("pearson_correlation", lambda: p.pearson_correlation(x=age, y=nihss_adm))
    run_step("quartiles", lambda: p.quartiles(variable=age))
    run_step("anova_oneway", lambda: p.anova_oneway(group_by=sex, outcome=age))
    run_step(
        "anova_twoway",
        lambda: p.anova_twoway(factor_a=sex, factor_b=acs_pcs.variable, outcome=age),
    )
    run_step(
        "mann_whitney_u_test",
        lambda: p.mann_whitney_u_test(
            variable=nihss_adm,
            group_by=poor.variable,
            group_a="Yes",
            group_b="No",
        ),
    )
    run_step(
        "outlier_report",
        lambda: p.outlier_report(
            variables=[age, nihss_adm],
            strategies={age: "iqr", nihss_adm: "gaussian"},
            tails={age: "both", nihss_adm: "both"},
        ),
    )


# %%
def run_models(ctx: dict[str, Any]) -> None:
    p = ctx["pipeline"]
    age = ctx["age"]
    sex = ctx["sex"]
    nihss_adm = ctx["nihss_adm"]
    poor = ctx["poor"]

    run_step(
        "linear_regression",
        lambda: p.linear_regression(x=[age, sex], y=nihss_adm),
    )
    run_step(
        "linear_regression_cv",
        lambda: p.linear_regression_cv(x=[age, sex], y=nihss_adm, n_splits=3),
    )
    run_step(
        "logistic_regression",
        lambda: p.logistic_regression(
            x=[age, sex, nihss_adm],
            y=poor.variable,
            positive_class="Yes",
        ),
    )
    run_step(
        "logistic_regression_cv",
        lambda: p.logistic_regression_cv(
            x=[age, sex, nihss_adm],
            y=poor.variable,
            positive_class="Yes",
            n_splits=3,
        ),
    )

    # Survival / mixed models often need variables SSR does not expose in this cohort.
    run_step(
        "cox_regression_classical",
        lambda: p.cox_regression_classical(
            time=age,
            event_var=poor.variable,
            covariates=[sex, nihss_adm],
            positive_class="Yes",
        ),
    )
    run_step(
        "cox_regression_stacked",
        lambda: p.cox_regression_stacked(
            time=age,
            event_var=poor.variable,
            covariates=[sex, nihss_adm],
            positive_class="Yes",
            n_time_bins=5,
        ),
    )
    run_step(
        "lmm",
        lambda: p.lmm(
            outcome=nihss_adm,
            covariates=[age],
            grouping_var=[sex],
        ),
    )
    run_step(
        "glmm_binary",
        lambda: p.glmm_binary(
            outcome=poor.variable,
            covariates=[age, nihss_adm],
            grouping_var=[sex],
            positive_class="Yes",
        ),
    )
    run_step(
        "glmm_ordinal",
        lambda: p.glmm_ordinal(
            outcome=ctx["dm"].variables["Clinical syndrome"],
            covariates=[age],
            grouping_var=[sex],
            category_order=["1", "2", "4"],
        ),
    )
    run_step(
        "linear_svm",
        lambda: p.linear_svm(features=[age, nihss_adm], target=sex),
    )


# %%
def run_ml(ctx: dict[str, Any]) -> None:
    p = ctx["pipeline"]
    age = ctx["age"]
    sex = ctx["sex"]
    nihss_adm = ctx["nihss_adm"]
    nihss_24h = ctx["nihss_24h"]
    ivt = ctx["ivt"]
    evt = ctx["evt"]
    poor = ctx["poor"]

    run_step("kmeans", lambda: p.kmeans(features=[age, nihss_adm, nihss_24h], k=3))
    run_step("pca", lambda: p.pca(variables=[age, nihss_adm, nihss_24h]))
    run_step(
        "pca_with_transformation",
        lambda: p.pca_with_transformation(
            variables=[age, nihss_adm, nihss_24h],
            data_transformation={"center": [age, nihss_adm, nihss_24h]},
        ),
    )
    run_step(
        "naive_bayes_gaussian",
        lambda: p.naive_bayes_gaussian(features=[age, nihss_adm], target=sex),
    )
    run_step(
        "naive_bayes_categorical",
        lambda: p.naive_bayes_categorical(features=[ivt, evt], target=sex),
    )
    run_step(
        "naive_bayes_gaussian_cv",
        lambda: p.naive_bayes_gaussian_cv(features=[age, nihss_adm], target=sex, n_splits=3),
    )
    run_step(
        "naive_bayes_categorical_cv",
        lambda: p.naive_bayes_categorical_cv(features=[ivt, evt], target=sex, n_splits=3),
    )


# %%
def main() -> None:
    client = mip.Client.from_env()
    ctx = build_context(client)

    print_header("Pipeline catalog")
    methods = ctx["pipeline"].available_algorithms()
    print(f"  Typed Pipeline methods: {len(methods)}")

    show_preprocessing_stack(ctx)
    run_statistics(ctx)
    run_models(ctx)
    run_ml(ctx)

    print("\nDone. See docs/llm/wiki/07-pipeline-algorithms.md for call signatures.")


if __name__ == "__main__":
    main()
