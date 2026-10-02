"""Raw-first result wrappers with notebook-friendly previews."""

from __future__ import annotations

from typing import Any

from .display import HelpText
from .display import histogram_bins_counts
from .display import normalize_result_kind
from .display import render_result_card
from .display import result_highlights
from .display import result_table_rows
from .display import safe_numeric_list
from .display import show_help
from .display import to_frame
from .exceptions import UnsupportedOperationError
from .sklearn import feature_schema_from_logistic_result
from .sklearn import logistic_regression_to_sklearn

_PLOTTABLE_KINDS = frozenset(
    {
        "histogram",
        "describe",
        "t_test",
        "one_sample_t_test",
        "paired_t_test",
        "mann_whitney_u_test",
        "chi_square_test",
        "fisher_exact",
        "pearson_correlation",
        "logistic_regression",
        "logistic_regression_cv",
        "linear_regression",
        "linear_regression_cv",
    }
)


class Result:
    """Backend result wrapper with minimal notebook helpers."""

    def __init__(self, *, raw: Any, payload: Any = None, result_type: str | None = None):
        self.raw = raw
        self.payload = payload if payload is not None else raw
        self.result_type = result_type

    def summary(self) -> Any:
        return self.raw

    def highlights(self) -> dict[str, Any]:
        """Return compact key metrics for this result type."""
        return result_highlights(self.result_type, self.raw)

    def to_frame(self):
        """Return a tabular preview of the primary result table when available."""
        rows = result_table_rows(self.result_type, self.raw)
        if not rows:
            raise UnsupportedOperationError(
                f"No tabular preview is available for result type {self.result_type!r}. "
                "Use .summary() or .raw for the backend payload."
            )
        return to_frame(rows)

    def _repr_html_(self) -> str:
        methods = [".highlights()", ".to_frame()", ".summary()", ".raw", ".payload", ".help()"]
        if normalize_result_kind(self.result_type) in _PLOTTABLE_KINDS:
            methods.insert(2, ".plot()")
        return render_result_card(result_type=self.result_type, raw=self.raw, methods=methods)

    def help(self) -> HelpText:
        return show_help("Result")

    def plot(self):
        """Render a matplotlib chart for supported result types."""
        try:
            import matplotlib.pyplot as plt
        except Exception as exc:
            raise UnsupportedOperationError("Plotting requires matplotlib to be installed.") from exc

        kind = normalize_result_kind(self.result_type)
        if kind == "histogram":
            return _plot_histogram(plt, self.raw)
        if kind == "describe":
            return _plot_describe(plt, self.raw)
        if kind in {"t_test", "one_sample_t_test", "paired_t_test", "mann_whitney_u_test"}:
            return _plot_effect(plt, self.raw, kind=kind)
        if kind in {"chi_square_test", "fisher_exact"}:
            return _plot_association(plt, self.raw, kind=kind)
        if kind == "pearson_correlation":
            return _plot_pearson(plt, self.raw)
        if kind in {"logistic_regression", "logistic_regression_cv"}:
            return _plot_logistic(plt, self.raw)
        if kind in {"linear_regression", "linear_regression_cv"}:
            return _plot_coefficients(plt, self.raw, title="Linear regression coefficients")
        raise UnsupportedOperationError(f"Plotting is not supported for result type {self.result_type!r}.")


class ModelResult(Result):
    """Model result with logistic-regression sklearn export support."""

    def __init__(
        self,
        *,
        raw: Any,
        payload: Any = None,
        result_type: str | None = None,
        positive_class: Any = None,
    ):
        super().__init__(raw=raw, payload=payload, result_type=result_type)
        self.positive_class = positive_class

    def feature_schema(self) -> dict[str, Any]:
        return feature_schema_from_logistic_result(self.raw)

    def to_sklearn(self):
        if self.result_type != "logistic_regression":
            raise UnsupportedOperationError("Only logistic regression results can be exported to sklearn.")
        return logistic_regression_to_sklearn(self.raw, positive_class=self.positive_class)

    def _repr_html_(self) -> str:
        methods = [
            ".highlights()",
            ".to_frame()",
            ".plot()",
            ".summary()",
            ".feature_schema()",
            ".to_sklearn()",
            ".help()",
        ]
        return render_result_card(result_type=self.result_type, raw=self.raw, methods=methods)

    def help(self) -> HelpText:
        return show_help("ModelResult")


def _histogram_data(raw: Any):
    payload = raw if isinstance(raw, dict) else {}
    bins, counts = histogram_bins_counts(payload)
    if not bins or not counts:
        return None
    return bins, counts


def _histogram_variable(raw: Any) -> str | None:
    payload = raw if isinstance(raw, dict) else {}
    for key in ("variable", "var", "label"):
        value = payload.get(key)
        if value:
            return str(value)
    histogram = payload.get("histogram")
    if isinstance(histogram, dict):
        for key in ("variable", "var", "label"):
            value = histogram.get(key)
            if value:
                return str(value)
    if isinstance(histogram, list) and histogram and isinstance(histogram[0], dict):
        for key in ("variable", "var", "label"):
            value = histogram[0].get(key)
            if value:
                return str(value)
    return None


def _plot_histogram(plt, raw: Any):
    data = _histogram_data(raw)
    if data is None:
        raise UnsupportedOperationError("This histogram result does not contain plottable bins/counts data.")
    bins, counts = data
    counts = safe_numeric_list(counts)
    variable = _histogram_variable(raw)
    labels = [str(item) for item in bins]
    if len(bins) == len(counts) + 1:  # numeric histograms return bin edges, one more than bars
        edges = safe_numeric_list(bins)
        labels = [f"{low:g}-{high:g}" for low, high in zip(edges, edges[1:])]
    figure, axis = plt.subplots()
    axis.bar(range(len(counts)), counts, tick_label=labels)
    axis.set_ylabel("count")
    axis.set_xlabel(variable or "bin")
    axis.set_title(f"Histogram{f': {variable}' if variable else ''}")
    if len(bins) > 8:
        axis.tick_params(axis="x", labelrotation=45)
    figure.tight_layout()
    return axis


def _plot_describe(plt, raw: Any):
    rows = result_table_rows("describe", raw)
    plot_rows = [row for row in rows if row.get("mean") is not None]
    if not plot_rows:
        raise UnsupportedOperationError("This describe result has no numeric means to plot.")
    labels = [str(row.get("variable") or "") for row in plot_rows]
    means = [float(row["mean"]) for row in plot_rows]
    figure, axis = plt.subplots(figsize=(max(6, 0.45 * len(labels)), 4))
    axis.barh(range(len(means)), means)
    axis.set_yticks(range(len(labels)))
    axis.set_yticklabels(labels)
    axis.set_xlabel("mean")
    axis.set_title("Describe: variable means")
    figure.tight_layout()
    return axis


def _plot_effect(plt, raw: Any, *, kind: str):
    payload = raw if isinstance(raw, dict) else {}
    if "mean_diff" in payload:
        estimate = float(payload["mean_diff"])
        low = payload.get("ci_lower")
        high = payload.get("ci_upper")
        label = "mean difference"
        ref = 0.0
    elif "t_stat" in payload:
        estimate = float(payload["t_stat"])
        low = high = None
        label = "t statistic"
        ref = 0.0
    elif "u_stat" in payload:
        estimate = float(payload["u_stat"])
        low = high = None
        label = "U statistic"
        ref = None
    else:
        raise UnsupportedOperationError(f"This {kind} result does not contain plottable effect estimates.")

    figure, axis = plt.subplots(figsize=(6, 2.2))
    xerr = None
    if low is not None and high is not None:
        xerr = [[estimate - float(low)], [float(high) - estimate]]
    axis.errorbar([estimate], [0], xerr=xerr, fmt="o", capsize=4)
    if ref is not None:
        axis.axvline(ref, linestyle="--", linewidth=1)
    axis.set_yticks([0])
    axis.set_yticklabels([kind])
    axis.set_xlabel(label)
    p_value = payload.get("p", payload.get("p_value"))
    title = f"{kind.replace('_', ' ')}"
    if p_value is not None:
        title += f" (p={p_value})"
    axis.set_title(title)
    figure.tight_layout()
    return axis


def _plot_association(plt, raw: Any, *, kind: str):
    payload = raw if isinstance(raw, dict) else {}
    if "chi2" in payload:
        value = float(payload["chi2"])
        label = "chi²"
    elif "odds_ratio" in payload:
        value = float(payload["odds_ratio"])
        label = "odds ratio"
    else:
        raise UnsupportedOperationError(f"This {kind} result does not contain a plottable association statistic.")
    figure, axis = plt.subplots(figsize=(5, 2.5))
    axis.bar([label], [value])
    axis.set_ylabel(label)
    p_value = payload.get("p_value", payload.get("p"))
    title = kind.replace("_", " ")
    if p_value is not None:
        title += f" (p={p_value})"
    axis.set_title(title)
    figure.tight_layout()
    return axis


def _plot_pearson(plt, raw: Any):
    rows = result_table_rows("pearson_correlation", raw)
    if len(rows) == 1 and "correlation" in rows[0] and "pair" not in rows[0]:
        figure, axis = plt.subplots(figsize=(5, 2.5))
        axis.bar(["correlation"], [float(rows[0]["correlation"])])
        axis.set_ylim(-1, 1)
        axis.axhline(0, linestyle="--", linewidth=1)
        axis.set_title("Pearson correlation")
        figure.tight_layout()
        return axis

    labels = []
    values = []
    for row in rows:
        if "correlation" in row:
            labels.append(str(row.get("pair") or row.get("title") or "corr"))
            values.append(float(row["correlation"]))
        else:
            for key, value in row.items():
                if key.lower() in {"correlation", "r", "corr"} or isinstance(value, (int, float)):
                    labels.append(str(row.get("pair") or key))
                    values.append(float(value))
                    break
    if not values:
        raise UnsupportedOperationError("This pearson_correlation result does not contain plottable correlations.")
    figure, axis = plt.subplots(figsize=(max(5, 0.5 * len(values)), 3.5))
    axis.bar(range(len(values)), values, tick_label=labels)
    axis.axhline(0, linestyle="--", linewidth=1)
    axis.set_ylabel("correlation")
    axis.set_title("Pearson correlations")
    if len(labels) > 6:
        axis.tick_params(axis="x", labelrotation=45)
    figure.tight_layout()
    return axis


def _plot_logistic(plt, raw: Any):
    rows = result_table_rows("logistic_regression", raw)
    plot_rows = [row for row in rows if str(row.get("feature") or "").lower() not in {"intercept", "const"}]
    if not plot_rows or any(row.get("odds_ratio") is None for row in plot_rows):
        raise UnsupportedOperationError("This logistic regression result does not contain plottable odds ratios.")
    plot_rows = list(reversed(plot_rows))
    labels = [str(row["feature"]) for row in plot_rows]
    odds = [float(row["odds_ratio"]) for row in plot_rows]
    lower = [float(row["or_lower_ci"]) if row.get("or_lower_ci") is not None else float(row["odds_ratio"]) for row in plot_rows]
    upper = [float(row["or_upper_ci"]) if row.get("or_upper_ci") is not None else float(row["odds_ratio"]) for row in plot_rows]
    y_pos = range(len(plot_rows))
    figure, axis = plt.subplots(figsize=(8, max(3, 0.45 * len(plot_rows))))
    axis.errorbar(
        odds,
        list(y_pos),
        xerr=[[o - lo for o, lo in zip(odds, lower)], [hi - o for o, hi in zip(odds, upper)]],
        fmt="o",
        capsize=4,
    )
    axis.axvline(1, linestyle="--", linewidth=1)
    axis.set_xscale("log")
    axis.set_yticks(list(y_pos))
    axis.set_yticklabels(labels)
    axis.set_xlabel("odds ratio (log scale)")
    axis.set_title("Logistic regression odds ratios")
    figure.tight_layout()
    return axis


def _plot_coefficients(plt, raw: Any, *, title: str):
    rows = result_table_rows("linear_regression", raw)
    plot_rows = [row for row in rows if row.get("coefficient") is not None]
    if not plot_rows:
        raise UnsupportedOperationError("This regression result does not contain plottable coefficients.")
    labels = [str(row.get("feature") or "") for row in plot_rows]
    values = [float(row["coefficient"]) for row in plot_rows]
    figure, axis = plt.subplots(figsize=(max(6, 0.45 * len(labels)), 4))
    axis.barh(range(len(values)), values)
    axis.set_yticks(range(len(labels)))
    axis.set_yticklabels(labels)
    axis.axvline(0, linestyle="--", linewidth=1)
    axis.set_xlabel("coefficient")
    axis.set_title(title)
    figure.tight_layout()
    return axis
