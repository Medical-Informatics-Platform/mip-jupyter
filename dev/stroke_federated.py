"""Stroke 3.7 federated analysis helpers: dataset selection and coverage checks."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

SSR_AGGREGATE = "SSR"
SSR_PARTITIONS = frozenset({"SSR-even", "SSR-odd"})


@dataclass(frozen=True)
class VariableCoverage:
    """Aggregate completeness for one variable on one dataset slice."""

    label: str
    variable_code: str
    dataset: str
    num_dtps: float
    num_total: float
    completeness: float

    @property
    def has_data(self) -> bool:
        return self.num_dtps > 0 and self.num_total > 0

    def meets_threshold(self, min_fraction: float) -> bool:
        return self.has_data and self.completeness >= min_fraction


def normalize_dataset_labels(labels: Iterable[str]) -> list[str]:
    return [label.strip() for label in labels if label and label.strip()]


def select_primary_datasets(
    labels: Sequence[str],
    *,
    mode: str = "aggregate",
) -> list[str]:
    """
    Choose Stroke SSR datasets without double-counting partitions.

    mode:
      - ``aggregate``: SSR only (default for primary analyses)
      - ``partitions``: SSR-even and SSR-odd only (sensitivity analyses)
    """
    normalized = normalize_dataset_labels(labels)
    if not normalized:
        raise ValueError("At least one dataset label is required.")

    has_aggregate = SSR_AGGREGATE in normalized
    has_partition = any(label in SSR_PARTITIONS for label in normalized)

    if has_aggregate and has_partition:
        raise ValueError(
            "Do not combine SSR with SSR-even/SSR-odd; choose aggregate or partitions."
        )

    if mode == "aggregate":
        if has_partition and not has_aggregate:
            raise ValueError(
                "Partition-only selection is not allowed in aggregate mode; "
                "use mode='partitions' for sensitivity analyses."
            )
        return [SSR_AGGREGATE] if SSR_AGGREGATE in normalized else list(normalized)

    if mode == "partitions":
        selected = [label for label in normalized if label in SSR_PARTITIONS]
        if not selected:
            raise ValueError("Partition mode requires SSR-even and/or SSR-odd.")
        if has_aggregate:
            raise ValueError("Partition mode cannot include SSR aggregate.")
        return selected

    raise ValueError(f"Unknown dataset selection mode: {mode!r}")


def coverage_from_featurewise(
    summary: Mapping[str, Any],
    *,
    dataset: str = SSR_AGGREGATE,
    label_by_code: Mapping[str, str] | None = None,
) -> list[VariableCoverage]:
    """Parse describe().summary() featurewise rows for one dataset."""
    rows: list[VariableCoverage] = []
    label_by_code = label_by_code or {}
    for item in summary.get("featurewise", []):
        if item.get("dataset") != dataset:
            continue
        code = str(item.get("variable", ""))
        data = item.get("data") or {}
        num_dtps = float(data.get("num_dtps", 0) or 0)
        num_total = float(data.get("num_total", 0) or 0)
        completeness = (num_dtps / num_total) if num_total else 0.0
        rows.append(
            VariableCoverage(
                label=label_by_code.get(code, code),
                variable_code=code,
                dataset=dataset,
                num_dtps=num_dtps,
                num_total=num_total,
                completeness=completeness,
            )
        )
    return rows


def assess_required_variables(
    coverage_rows: Sequence[VariableCoverage],
    *,
    required_labels: Sequence[str],
    min_fraction: float = 0.10,
) -> tuple[list[VariableCoverage], list[str]]:
    """
    Return (ok, missing) for required catalog labels.

    missing contains labels with no SSR aggregate data or below min_fraction.
    """
    by_label = {row.label: row for row in coverage_rows}
    ok: list[VariableCoverage] = []
    missing: list[str] = []
    for label in required_labels:
        row = by_label.get(label)
        if row is None or not row.meets_threshold(min_fraction):
            missing.append(label)
        else:
            ok.append(row)
    return ok, missing


def parse_logistic_regression_summary(
    payload: Mapping[str, Any],
    *,
    label_by_code: Mapping[str, str] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """
    Parse logistic_regression().summary() into model metadata and coefficient rows.

    Use this instead of ad-hoc key guessing (feature_schema, top-level n_obs, etc.).
    """
    label_by_code = label_by_code or {}
    model = payload.get("summary") or {}
    rows: list[dict[str, Any]] = []
    for term, coef, se, lo, hi, p in zip(
        payload.get("indep_vars") or [],
        model.get("coefficients") or [],
        model.get("stderr") or [],
        model.get("lower_ci") or [],
        model.get("upper_ci") or [],
        model.get("pvalues") or [],
    ):
        or_val = math.exp(coef) if coef is not None else None
        or_lo = math.exp(lo) if lo is not None else None
        or_hi = math.exp(hi) if hi is not None else None
        rows.append(
            {
                "term": label_by_code.get(str(term), str(term)),
                "beta": coef,
                "or": or_val,
                "se": se,
                "beta_lower_ci": lo,
                "beta_upper_ci": hi,
                "or_lower_ci": or_lo,
                "or_upper_ci": or_hi,
                "p_value": p,
            }
        )
    meta = {
        "n_obs": model.get("n_obs"),
        "r_squared_mcf": model.get("r_squared_mcf"),
        "r_squared_cs": model.get("r_squared_cs"),
        "aic": model.get("aic"),
        "bic": model.get("bic"),
    }
    return meta, rows


def format_logistic_term(row: Mapping[str, Any]) -> str:
    """Human-readable OR (95% CI) and p-value for one coefficient row."""
    term = str(row.get("term", ""))
    or_val = row.get("or")
    or_lo = row.get("or_lower_ci")
    or_hi = row.get("or_upper_ci")
    p = row.get("p_value")
    if or_val is None:
        return f"{term}: n/a"
    ci_part = ""
    if or_lo is not None and or_hi is not None:
        ci_part = f" (95% CI {or_lo:.3f}-{or_hi:.3f})"
    p_part = f", p={p}" if p is not None else ""
    return f"{term}: OR={or_val:.3f}{ci_part}{p_part}"
