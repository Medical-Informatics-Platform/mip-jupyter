"""Notebook display helpers: help text, HTML cards, and tabular previews."""

from __future__ import annotations

import math
from typing import Any
from typing import Iterable
from typing import Mapping
from typing import Sequence

from .catalog_registry import PIPELINE_BACKEND_ALGORITHMS
from .labels import public_label

_BACKEND_TO_METHOD = {backend: method for method, backend in PIPELINE_BACKEND_ALGORITHMS.items()}


def normalize_result_kind(result_type: str | None) -> str:
    """Map backend algorithm names to public Pipeline method names when needed."""
    kind = str(result_type or "").strip().lower()
    if not kind:
        return ""
    if kind in PIPELINE_BACKEND_ALGORITHMS:
        return kind
    return _BACKEND_TO_METHOD.get(kind, kind)

HELP_TEXT: dict[str, str] = {
    "Client": """\
Client help

Useful methods:
- client.catalog()       browse data models, datasets, and variables
- client.algorithms()    search available algorithms
- client.experiments()   list or run persisted experiments

Typical next step:
  catalog = client.catalog()
  catalog.summaries()""",
    "Catalog": """\
Catalog help

Useful methods:
- catalog.summaries()         compact list of data models
- catalog.tree()              collapsible HTML / ASCII overview of all models
- catalog.browse()            interactive picker (requires ipywidgets)
- catalog.data_model("Dementia")  pick one model to explore
- catalog.list()              all DataModel objects

Typical next step:
  dm = catalog.data_model("Dementia")
  dm.summary()""",
    "DataModel": """\
DataModel help

Useful methods:
- dm.summary()                high-level counts and metadata
- dm.list_datasets()          dataset summaries as dicts
- dm.datasets.list()          Dataset objects
- dm.list_variables()         variable summaries as dicts
- dm.variables.search("Age")  find variables by name
- dm.variables.numerical()    numeric variables only
- dm.variables.categorical()  categorical variables only
- dm.tree()                   collapsible HTML hierarchy (ASCII via str())
- dm.select(datasets=[...], variables=[...])  build an AnalysisSet
- dm.browse()                 interactive picker (requires ipywidgets)
- dm.variables.tree(group="Demographics")

Typical next step:
  analysis_set = dm.select(datasets=["ADNI"], variables=["Age", "MMSE"])
  pipeline = mip.Pipeline(analysis_set=analysis_set)""",
    "Dataset": """\
Dataset help

Useful methods:
- dataset.summary()       label and variable count
- dataset.details()       label-safe metadata
- dataset.variables()     variables available in this dataset
- dataset.has_variable(v) check whether a variable is present

Typical next step:
  adni = dm.datasets["ADNI"]
  adni.variables()""",
    "DatasetCollection": """\
DatasetCollection help

Useful methods:
- dm.datasets.list()          all datasets
- dm.datasets.search("ADNI")  find datasets by name
- dm.datasets.to_frame()      tabular preview
- dm.datasets["ADNI"]         pick one dataset

Typical next step:
  adni = dm.datasets["ADNI"]""",
    "Variable": """\
Variable help

Useful methods:
- variable.summary()    label, type, numerical/categorical flags
- variable.details()    label-safe metadata and categories
- variable.categories() allowed category labels (if categorical)

Typical next step:
  age = dm.variables["Age"]
  age.summary()""",
    "VariableCollection": """\
VariableCollection help

Useful methods:
- dm.variables.search("Age")     find by label
- dm.variables.numerical()       numeric variables only
- dm.variables.categorical()     categorical variables only
- dm.variables.to_frame()        tabular preview
- dm.variables.tree(group="Demographics")   group hierarchy
- dm.variables["Age"]           pick one variable

Typical next step:
  age = dm.variables["Age"]""",
    "AnalysisSet": """\
AnalysisSet help

Useful methods:
- analysis_set.summary()   selected model, datasets, variables
- analysis_set.explain()     inputdata payload preview
- analysis_set.histogram()   quick one-off histogram (via Pipeline)

Typical next step:
  pipeline = mip.Pipeline(analysis_set=analysis_set, filters=...)
  pipeline.explain()""",
    "Pipeline": """\
Pipeline help

Useful methods:
- pipeline.explain()              full request preview
- pipeline.summary()              analysis set + filters + preprocessing
- pipeline.available_algorithms() list callable algorithm methods
- pipeline.recommend_algorithms() suggested next steps
- pipeline.describe()             summary statistics
- pipeline.histogram(variable=...) distribution plot data
- pipeline.pearson_correlation(x=..., y=...)
- pipeline.logistic_regression(x=[...], y=..., positive_class=...)

Typical next step:
  pipeline.recommend_algorithms()
  result = pipeline.histogram(variable=mmse, bins=20)""",
    "Result": """\
Result help

Useful methods:
- result.highlights() key metrics for this algorithm
- result.to_frame()   tabular preview of the main result table
- result.summary()    backend result payload (same as .raw)
- result.raw          raw result dict or value
- result.payload      full experiment response
- result.plot()       matplotlib chart (histogram, describe, t-test, chi-square,
                      pearson, logistic odds-ratio forest, …)

Typical next step:
  result.to_frame()
  result.plot()""",
    "ModelResult": """\
ModelResult help

Useful methods:
- result.highlights()     key metrics (N, coefficient count, …)
- result.to_frame()       coefficient table with odds ratios / p-values / CIs
- result.plot()           odds-ratio forest plot
- result.summary()        backend result payload
- result.raw              raw result dict
- result.payload          full experiment response
- result.feature_schema() feature names from logistic regression
- result.to_sklearn()     export as sklearn classifier (logistic only)

Typical next step:
  result.to_frame()
  result.plot()""",
    "AlgorithmRegistry": """\
AlgorithmRegistry help

Useful methods:
- client.algorithms().list()          all algorithms
- client.algorithms().search("text")  find by name or description
- client.algorithms().to_frame()      tabular preview
- client.algorithms().statistics()    statistical algorithms
- client.algorithms().models()        modelling algorithms

Typical next step:
  client.algorithms().search("logistic")""",
}


def escape_html(text: Any) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def render_object_card(
    title: str,
    fields: Mapping[str, Any],
    methods: Sequence[str] | None = None,
) -> str:
    """Render a compact HTML card for JupyterLab object display."""
    rows = "".join(
        f"<tr><th>{escape_html(key)}</th><td>{escape_html(value)}</td></tr>"
        for key, value in fields.items()
    )
    methods_html = ""
    if methods:
        items = "".join(f"<li><code>{escape_html(item)}</code></li>" for item in methods)
        methods_html = f"<p><strong>Useful methods</strong></p><ul>{items}</ul>"
    return (
        f'<div style="font-family:monospace;font-size:13px;line-height:1.4">'
        f"<p><strong>{escape_html(title)}</strong></p>"
        f"<table>{rows}</table>{methods_html}</div>"
    )


def format_help(kind: str) -> str:
    try:
        return HELP_TEXT[kind]
    except KeyError as exc:
        raise ValueError(f"No help text registered for {kind!r}") from exc


class HelpText:
    """Notebook-friendly help text returned by object .help() methods."""

    def __init__(self, text: str):
        self._text = text

    def __str__(self) -> str:
        return self._text

    def _repr_html_(self) -> str:
        escaped = escape_html(self._text)
        return f"<pre style=\"white-space:pre-wrap\">{escaped}</pre>"

    def _repr_pretty_(self, p, cycle) -> None:
        if cycle:
            p.text("HelpText(...)")
            return
        p.text(self._text)


def show_help(kind: str) -> HelpText:
    return HelpText(format_help(kind))


def _summary_row(item: Any) -> dict[str, Any]:
    if hasattr(item, "summary") and callable(item.summary):
        summary = item.summary()
        if isinstance(summary, dict):
            return dict(summary)
    if isinstance(item, Mapping):
        return dict(item)
    return {"value": str(item)}


def to_frame(items: Iterable[Any]):
    """Convert variables, datasets, algorithms, or summary dicts to a DataFrame."""
    import pandas as pd

    rows = [_summary_row(item) for item in items]
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def recommend_pipeline_steps(variables: Sequence[Any]) -> RecommendationText:
    """Suggest pipeline methods based on selected variable types."""
    lines = ["Based on your selected variables:"]
    kinds: list[tuple[str, str]] = []
    numerical: list[Any] = []
    categorical: list[Any] = []
    steps: list[str] = [
        "pipeline.describe()",
        "pipeline.explain()",
        "pipeline.available_algorithms()",
    ]

    for variable in variables:
        label = public_label(variable)
        is_num = getattr(variable, "is_numerical", lambda: False)()
        is_cat = getattr(variable, "is_categorical", lambda: False)()
        if is_num:
            kind = "numerical"
            numerical.append(variable)
        elif is_cat:
            kind = "categorical"
            categorical.append(variable)
        else:
            kind = "unknown"
        kinds.append((label, kind))
        lines.append(f"- {label}: {kind}")

    lines.append("")
    lines.append("Possible next steps:")
    for step in steps:
        lines.append(f"- {step}")

    if numerical:
        first = public_label(numerical[0])
        step = f'pipeline.histogram(variable=variables["{first}"])'
        steps.append(step)
        lines.append(f"- {step}")
    if len(numerical) >= 2:
        x = public_label(numerical[0])
        y = public_label(numerical[1])
        step = f'pipeline.pearson_correlation(x=variables["{x}"], y=variables["{y}"])'
        steps.append(step)
        lines.append(f"- {step}")
    if categorical and numerical:
        xs = ", ".join(f'variables["{public_label(item)}"]' for item in numerical[:2])
        y = public_label(categorical[0])
        step = f'pipeline.logistic_regression(x=[{xs}], y=variables["{y}"], positive_class=...)'
        steps.append(step)
        lines.append(f"- {step}")
    elif len(categorical) >= 2:
        x = public_label(categorical[0])
        y = public_label(categorical[1])
        step = f'pipeline.chi_square_test(x=variables["{x}"], y=variables["{y}"])'
        steps.append(step)
        lines.append(f"- {step}")

    text = "\n".join(lines)
    kind_rows = "".join(
        f"<tr><td>{escape_html(label)}</td><td>{escape_html(kind)}</td></tr>"
        for label, kind in kinds
    )
    step_items = "".join(f"<li><code>{escape_html(step)}</code></li>" for step in steps)
    html = (
        '<div style="font-family:monospace;font-size:13px;line-height:1.4">'
        "<p><strong>Recommended next steps</strong></p>"
        f"<table><thead><tr><th>variable</th><th>kind</th></tr></thead>"
        f"<tbody>{kind_rows}</tbody></table>"
        f"<p><strong>Try</strong></p><ul>{step_items}</ul>"
        "</div>"
    )
    return RecommendationText(text, html=html)


class RecommendationText(str):
    """Notebook-friendly algorithm recommendations from Pipeline.recommend_algorithms()."""

    def __new__(cls, text: str, *, html: str | None = None):
        instance = super().__new__(cls, text)
        instance._html = html
        return instance

    def _repr_html_(self) -> str:
        if self._html:
            return self._html
        return f"<pre style=\"white-space:pre-wrap\">{escape_html(str(self))}</pre>"

    def _repr_pretty_(self, p, cycle) -> None:
        if cycle:
            p.text("RecommendationText(...)")
            return
        p.text(str(self))


_RESULT_TABLE_PREVIEW_ROWS = 12


def result_highlights(result_type: str | None, raw: Any) -> dict[str, Any]:
    """Pick a compact set of key metrics for notebook Result cards."""
    payload = raw if isinstance(raw, dict) else {}
    kind = normalize_result_kind(result_type)

    if kind == "describe":
        rows = payload.get("featurewise") or []
        return {
            "variables": len(rows) if isinstance(rows, list) else 0,
            "hint": "Use .to_frame() for per-variable stats",
        }

    if kind == "histogram":
        bins, counts = histogram_bins_counts(payload)
        total = safe_sum(counts)
        return {
            "bins": len(bins) if bins else 0,
            "total_count": _fmt_number(total),
            "hint": "Call .plot() for a bar chart",
        }

    if kind in {"t_test", "one_sample_t_test", "paired_t_test", "mann_whitney_u_test"}:
        return _pick_fields(
            payload,
            ("t_stat", "p", "mean_diff", "cohens_d", "n_obs", "df"),
        )

    if kind in {"chi_square_test", "fisher_exact"}:
        return _pick_fields(payload, ("chi2", "odds_ratio", "p_value", "dof", "n_obs"))

    if kind == "pearson_correlation":
        return _pick_fields(payload, ("title", "n_obs", "correlation", "p_value", "p"))

    if kind in {"logistic_regression", "logistic_regression_cv"}:
        summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else payload
        names = summary.get("feature_names") if isinstance(summary, dict) else None
        return {
            "n_obs": summary.get("n_obs") if isinstance(summary, dict) else None,
            "features": len(names) if isinstance(names, list) else None,
            "hint": "Use .to_frame() for coefficients",
        }

    if kind in {"linear_regression", "linear_regression_cv"}:
        return _pick_fields(payload, ("n_obs", "r2", "rmse", "intercept"))

    if kind == "kmeans":
        return _pick_fields(
            payload,
            ("k_selection", "selected_k", "n_obs_interval", "converged", "n_iter"),
        )

    if not payload:
        return {"hint": "Call .summary() for the backend payload"}
    keys = list(payload.keys())[:6]
    return {"keys": ", ".join(str(key) for key in keys), "hint": "Use .to_frame() or .summary()"}


def result_table_rows(result_type: str | None, raw: Any) -> list[dict[str, Any]]:
    """Normalize common algorithm payloads into tabular row dicts."""
    payload = raw if isinstance(raw, dict) else {}
    kind = normalize_result_kind(result_type)

    if kind == "describe":
        return _describe_rows(payload)
    if kind == "histogram":
        return _histogram_rows(payload)
    if kind in {"logistic_regression", "logistic_regression_cv"}:
        return _logistic_rows(payload)
    if kind in {"t_test", "one_sample_t_test", "paired_t_test", "mann_whitney_u_test"}:
        return [
            _pick_fields(
                payload,
                (
                    "t_stat",
                    "u_stat",
                    "p",
                    "p_value",
                    "mean_diff",
                    "ci_lower",
                    "ci_upper",
                    "cohens_d",
                    "n_obs",
                    "df",
                    "n1",
                    "n2",
                    "z_score",
                ),
            )
        ]
    if kind in {"chi_square_test", "fisher_exact"}:
        return [_pick_fields(payload, ("chi2", "odds_ratio", "p_value", "dof", "n_obs"))]
    if kind == "pearson_correlation":
        return _pearson_rows(payload)
    if kind in {"linear_regression", "linear_regression_cv"}:
        return _linear_rows(payload)
    if kind == "kmeans":
        return _kmeans_rows(payload)
    if kind == "standardized_mean_difference":
        return [
            {
                "group1": comparison.get("group1"),
                "group2": comparison.get("group2"),
                "smd": comparison.get("smd"),
            }
            for comparison in payload.get("comparisons") or []
        ]
    return []


def render_result_card(
    *,
    result_type: str | None,
    raw: Any,
    methods: Sequence[str] | None = None,
) -> str:
    """Render an algorithm-aware HTML card for a Result object."""
    highlights = {
        key: value
        for key, value in result_highlights(result_type, raw).items()
        if value is not None and value != ""
    }
    title = f"Result: {result_type or 'unknown'}"
    rows = result_table_rows(result_type, raw)
    preview = _render_html_table(rows[:_RESULT_TABLE_PREVIEW_ROWS])
    card = render_object_card(title, highlights, methods)
    if not preview:
        return card
    return f"{card}<p><strong>Preview</strong></p>{preview}"


def _pick_fields(payload: Mapping[str, Any], keys: Sequence[str]) -> dict[str, Any]:
    return {key: _fmt_number(payload.get(key)) for key in keys if key in payload}


def _fmt_number(value: Any) -> Any:
    """Keep numeric values numeric so DataFrame stylers can format them."""
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        number = float(value)
        if number != number:  # NaN
            return number
        # Preserve integers that fit exactly; otherwise round for stable display.
        if isinstance(value, int) or number.is_integer():
            return int(number) if abs(number) < 1e15 else number
        return round(number, 10)
    return value


def safe_sum(values: Sequence[Any]) -> float | None:
    total = 0.0
    seen = False
    for value in values or []:
        if value is None:
            continue
        try:
            total += float(value)
        except (TypeError, ValueError):
            continue
        seen = True
    return total if seen else None


def safe_numeric_list(values: Sequence[Any]) -> list[float]:
    cleaned: list[float] = []
    for value in values or []:
        if value is None:
            cleaned.append(0.0)
            continue
        try:
            cleaned.append(float(value))
        except (TypeError, ValueError):
            cleaned.append(0.0)
    return cleaned


def _describe_rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in payload.get("featurewise") or []:
        if not isinstance(item, Mapping):
            continue
        data = item.get("data") if isinstance(item.get("data"), Mapping) else {}
        rows.append(
            {
                "variable": item.get("variable"),
                "dataset": item.get("dataset"),
                "n": data.get("num_dtps"),
                "mean": _fmt_number(data.get("mean")),
                "std": _fmt_number(data.get("std")),
                "min": _fmt_number(data.get("min")),
                "max": _fmt_number(data.get("max")),
            }
        )
    return rows


def histogram_bins_counts(payload: Mapping[str, Any]) -> tuple[list[Any], list[Any]]:
    """Extract plottable bins/counts from common histogram payload shapes."""
    bins = payload.get("bins") or payload.get("x")
    counts = payload.get("counts") or payload.get("y")
    histogram = payload.get("histogram")
    if bins is None and isinstance(histogram, dict):
        bins = histogram.get("bins")
        counts = histogram.get("counts")
    if bins is None and isinstance(histogram, list) and histogram:
        first = histogram[0]
        if isinstance(first, dict):
            bins = first.get("bins")
            counts = first.get("counts")
    if not bins or not counts:
        return [], []
    return list(bins), list(counts)


def _histogram_rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    bins, counts = histogram_bins_counts(payload)
    return [{"bin": bin_value, "count": count} for bin_value, count in zip(bins, counts)]


def _logistic_rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else payload
    if not isinstance(summary, Mapping):
        return []
    names = (
        summary.get("feature_names")
        or payload.get("feature_names")
        or payload.get("indep_vars")
        or []
    )
    coefficients = summary.get("coefficients") or payload.get("coefficients") or []
    if not isinstance(names, list) or not isinstance(coefficients, list) or not names:
        return []
    pvalues = summary.get("pvalues") or summary.get("p_values") or []
    lower = summary.get("lower_ci") or summary.get("conf_int_lower") or []
    upper = summary.get("upper_ci") or summary.get("conf_int_upper") or []
    rows: list[dict[str, Any]] = []
    for index, name in enumerate(names):
        coef = coefficients[index] if index < len(coefficients) else None
        row: dict[str, Any] = {
            "feature": name,
            "coefficient": _fmt_number(coef),
        }
        if coef is not None:
            try:
                row["odds_ratio"] = _fmt_number(math.exp(float(coef)))
            except (TypeError, ValueError, OverflowError):
                pass
        if isinstance(pvalues, list) and index < len(pvalues):
            row["p"] = _fmt_number(pvalues[index])
        if isinstance(lower, list) and index < len(lower):
            low = lower[index]
            row["lower_ci"] = _fmt_number(low)
            try:
                row["or_lower_ci"] = _fmt_number(math.exp(float(low)))
            except (TypeError, ValueError, OverflowError):
                pass
        if isinstance(upper, list) and index < len(upper):
            high = upper[index]
            row["upper_ci"] = _fmt_number(high)
            try:
                row["or_upper_ci"] = _fmt_number(math.exp(float(high)))
            except (TypeError, ValueError, OverflowError):
                pass
        rows.append(row)
    return rows


def _linear_rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    names = payload.get("feature_names") or payload.get("indep_vars") or []
    coefficients = payload.get("coefficients") or payload.get("coef") or []
    if isinstance(names, list) and isinstance(coefficients, list) and names:
        return [
            {
                "feature": name,
                "coefficient": _fmt_number(coefficients[index] if index < len(coefficients) else None),
            }
            for index, name in enumerate(names)
        ]
    return [_pick_fields(payload, ("n_obs", "r2", "rmse", "intercept"))]


def _kmeans_rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for cluster in payload.get("clusters") or []:
        row = {
            "cluster_id": cluster.get("cluster_id"),
            "cluster": cluster.get("label"),
            "size": cluster.get("size_interval"),
        }
        for feature, value in (cluster.get("center") or {}).items():
            row[f"center_{feature}" if feature in row else feature] = value
        rows.append(row)
    return rows


def _pearson_rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    correlations = payload.get("correlations")
    if isinstance(correlations, list):
        rows: list[dict[str, Any]] = []
        for item in correlations:
            if isinstance(item, Mapping):
                rows.append(dict(item))
        if rows:
            return rows
    if isinstance(correlations, Mapping):
        return [{"pair": key, "correlation": _fmt_number(value)} for key, value in correlations.items()]
    return [_pick_fields(payload, ("title", "n_obs", "correlation", "p_value", "p"))]


def _render_html_table(rows: Sequence[Mapping[str, Any]]) -> str:
    if not rows:
        return ""
    columns: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                columns.append(str(key))
    header = "".join(f"<th>{escape_html(column)}</th>" for column in columns)
    body_rows = []
    for row in rows:
        cells = "".join(f"<td>{escape_html(row.get(column, ''))}</td>" for column in columns)
        body_rows.append(f"<tr>{cells}</tr>")
    return (
        '<table style="border-collapse:collapse;font-family:monospace;font-size:12px">'
        f"<thead><tr>{header}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        "</table>"
    )
