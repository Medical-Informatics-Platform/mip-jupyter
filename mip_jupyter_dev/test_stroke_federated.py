"""Tests for Stroke federated dataset selection and coverage helpers."""

from __future__ import annotations

import pytest

from mip_jupyter_dev.stroke_federated import (
    SSR_AGGREGATE,
    assess_required_variables,
    coverage_from_featurewise,
    format_logistic_term,
    parse_logistic_regression_summary,
    select_primary_datasets,
)


def test_select_primary_datasets_aggregate_only() -> None:
    assert select_primary_datasets(["SSR"]) == ["SSR"]


def test_select_primary_datasets_rejects_aggregate_plus_partitions() -> None:
    with pytest.raises(ValueError, match="Do not combine SSR"):
        select_primary_datasets(["SSR", "SSR-even"])


def test_select_primary_datasets_partitions_mode() -> None:
    assert select_primary_datasets(
        ["SSR-even", "SSR-odd"], mode="partitions"
    ) == ["SSR-even", "SSR-odd"]


def test_select_primary_datasets_partitions_rejects_aggregate() -> None:
    with pytest.raises(ValueError, match="Do not combine SSR"):
        select_primary_datasets(["SSR", "SSR-even"], mode="partitions")


def test_coverage_from_featurewise_parses_ssr_rows() -> None:
    summary = {
        "featurewise": [
            {
                "variable": "age",
                "dataset": "SSR",
                "data": {"num_dtps": 100.0, "num_total": 200.0},
            },
            {
                "variable": "age",
                "dataset": "SSR-even",
                "data": {"num_dtps": 50.0, "num_total": 100.0},
            },
            {
                "variable": "prestr_af_previous",
                "dataset": "SSR",
                "data": {},
            },
        ]
    }
    rows = coverage_from_featurewise(summary, label_by_code={"age": "Age"})
    assert len(rows) == 2
    age = next(r for r in rows if r.label == "Age")
    assert age.completeness == 0.5
    empty = next(r for r in rows if r.variable_code == "prestr_af_previous")
    assert empty.num_dtps == 0.0
    assert not empty.has_data


def test_assess_required_variables_flags_missing_and_sparse() -> None:
    rows = coverage_from_featurewise(
        {
            "featurewise": [
                {
                    "variable": "age",
                    "dataset": "SSR",
                    "data": {"num_dtps": 90.0, "num_total": 100.0},
                },
                {
                    "variable": "sleepdur",
                    "dataset": "SSR",
                    "data": {"num_dtps": 2.0, "num_total": 100.0},
                },
            ]
        },
        label_by_code={"age": "Age", "sleepdur": "Prestroke sleep hours"},
    )
    ok, missing = assess_required_variables(
        rows, required_labels=["Age", "Prestroke sleep hours"], min_fraction=0.10
    )
    assert [r.label for r in ok] == ["Age"]
    assert missing == ["Prestroke sleep hours"]


def test_parse_logistic_regression_summary_extracts_or_and_meta() -> None:
    payload = {
        "indep_vars": ["age", "sex[1]"],
        "summary": {
            "coefficients": [0.1, -0.2],
            "stderr": [0.05, 0.06],
            "lower_ci": [0.0, -0.3],
            "upper_ci": [0.2, -0.1],
            "pvalues": [0.04, 0.001],
            "n_obs": 1000,
            "r_squared_mcf": 0.12,
        },
    }
    meta, rows = parse_logistic_regression_summary(
        payload, label_by_code={"age": "Age", "sex": "Sex"}
    )
    assert meta["n_obs"] == 1000
    assert meta["r_squared_mcf"] == 0.12
    assert rows[0]["term"] == "Age"
    assert rows[0]["or"] == pytest.approx(1.105, rel=1e-3)
    assert rows[0]["or_lower_ci"] == pytest.approx(1.0, rel=1e-3)
    assert rows[0]["or_upper_ci"] == pytest.approx(1.221, rel=1e-3)
    assert rows[1]["p_value"] == 0.001


def test_format_logistic_term_includes_or_ci() -> None:
    row = {
        "term": "Age",
        "or": 1.105,
        "or_lower_ci": 1.0,
        "or_upper_ci": 1.221,
        "p_value": 0.04,
    }
    text = format_logistic_term(row)
    assert "OR=1.105" in text
    assert "95% CI" in text
    assert "p=0.04" in text


def test_parse_logistic_regression_summary_handles_missing_values() -> None:
    payload = {
        "indep_vars": ["intercept"],
        "summary": {
            "coefficients": [None],
            "stderr": [None],
            "lower_ci": [None],
            "upper_ci": [None],
            "pvalues": [None],
            "n_obs": 10,
            "r_squared_mcf": None,
        },
    }
    meta, rows = parse_logistic_regression_summary(payload)
    assert meta["n_obs"] == 10
    assert rows[0]["or"] is None
    assert rows[0]["or_lower_ci"] is None
    assert format_logistic_term(rows[0]) == "intercept: n/a"
