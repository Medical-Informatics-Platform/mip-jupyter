"""scikit-learn export helpers for backend model results."""

from __future__ import annotations

from typing import Any

from .exceptions import UnsupportedOperationError


def feature_schema_from_logistic_result(raw: Any) -> dict[str, Any]:
    """Return the local prediction schema for a logistic regression result."""
    feature_names, _coefficients, _intercept = logistic_regression_parts(raw)
    return {
        "feature_names": feature_names,
        "input_type": "pandas.DataFrame",
        "requires_preprocessed_input": True,
        "rule": "Columns must match sklearn_model.feature_names_in_ exactly and in order.",
    }


def logistic_regression_to_sklearn(raw: Any, *, positive_class: Any = None):
    """Build a sklearn LogisticRegression instance from backend coefficients."""
    feature_names, coefficients, intercept = logistic_regression_parts(raw)
    try:
        import numpy as np
        from sklearn.linear_model import LogisticRegression
    except Exception as exc:
        raise UnsupportedOperationError("Exporting to sklearn requires scikit-learn and numpy.") from exc

    model = LogisticRegression()
    model.coef_ = np.asarray([coefficients], dtype=float)
    model.intercept_ = np.asarray([intercept], dtype=float)
    model.classes_ = np.asarray(_classes(raw, positive_class), dtype=object)
    model.n_features_in_ = len(feature_names)
    model.feature_names_in_ = np.asarray(feature_names, dtype=object)
    return model


def logistic_regression_parts(raw: Any) -> tuple[list[str], list[float], float]:
    """Extract feature names, coefficients, and intercept from backend output."""
    payload = raw if isinstance(raw, dict) else {}
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    feature_names = _feature_names(payload, summary)
    coefficients = summary.get("coefficients") or payload.get("coefficients") or payload.get("coef")
    if not feature_names or not coefficients:
        _raise_missing_logistic_export_data()

    coefficients = [float(value) for value in coefficients]
    has_intercept_name = bool(feature_names and feature_names[0].lower() in {"intercept", "const"})
    if has_intercept_name:
        feature_names = feature_names[1:]
        intercept = coefficients[0]
        coefficients = coefficients[1:]
    elif len(coefficients) == len(feature_names) + 1:
        intercept = coefficients[0]
        coefficients = coefficients[1:]
    elif len(coefficients) == len(feature_names):
        intercept = float(summary.get("intercept", payload.get("intercept", 0.0)) or 0.0)
    else:
        _raise_missing_logistic_export_data()

    if not feature_names or len(feature_names) != len(coefficients):
        _raise_missing_logistic_export_data()
    return [str(item) for item in feature_names], coefficients, float(intercept)


def _feature_names(payload: dict[str, Any], summary: dict[str, Any]) -> list[str]:
    names = summary.get("feature_names") or payload.get("feature_names") or payload.get("indep_vars")
    if not isinstance(names, list):
        return []
    return [str(item) for item in names]


def _classes(raw: Any, positive_class: Any) -> list[Any]:
    payload = raw if isinstance(raw, dict) else {}
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    for key in ("classes", "class_names"):
        values = payload.get(key) or summary.get(key)
        if isinstance(values, list) and len(values) == 2:
            return values
    positive = payload.get("positive_class") or summary.get("positive_class") or positive_class
    if positive is not None:
        return [f"not_{positive}", positive]
    return [0, 1]


def _raise_missing_logistic_export_data() -> None:
    raise UnsupportedOperationError(
        "Cannot export this logistic regression result to sklearn because feature names or coefficients are missing."
    )
