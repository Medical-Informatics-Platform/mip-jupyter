"""Build AnalysisRequestDTO experiment payloads for platform-backend."""

from __future__ import annotations

from typing import Any
from typing import Iterable
from typing import Sequence

from .derived import DerivedVariable
from .labels import internal_code
from .preprocessing import LONGITUDINAL_REQUIRED_VARIABLES
from .preprocessing import MissingValuesHandler


def code(value: Any) -> str:
    return internal_code(value)


def is_derived_variable(value: Any) -> bool:
    return isinstance(value, DerivedVariable)


def collect_filter_fields(filters: Any) -> set[str]:
    fields: set[str] = set()
    if filters is None:
        return fields
    payload = filters.explain() if hasattr(filters, "explain") else filters
    if not isinstance(payload, dict):
        return fields
    _walk_filter_fields(payload, fields)
    return fields


def _walk_filter_fields(node: dict[str, Any], fields: set[str]) -> None:
    if "condition" in node:
        for rule in node.get("rules") or []:
            if isinstance(rule, dict):
                _walk_filter_fields(rule, fields)
        return
    field = node.get("field") or node.get("id")
    if field:
        fields.add(str(field))


def collect_source_variables(
    *,
    analysis_set_variables: Sequence[Any],
    filters: Any = None,
    longitudinal: Any = None,
    handle_missing: Any = None,
    outlier_handling: Any = None,
    new_columns: Sequence[Any] | None = None,
    algorithm_x: Sequence[Any] | None = None,
    algorithm_y: Sequence[Any] | None = None,
) -> list[str]:
    """Union of raw source column codes available before preprocessing."""
    derived_codes = _derived_codes(new_columns)
    variables: list[str] = []
    seen: set[str] = set()

    def add(value: Any) -> None:
        item = code(value)
        if not item or item in seen or item in derived_codes:
            return
        if is_derived_variable(value):
            return
        seen.add(item)
        variables.append(item)

    for variable in analysis_set_variables:
        add(variable)
    for field in collect_filter_fields(filters):
        add(field)
    if longitudinal is not None:
        for required in LONGITUDINAL_REQUIRED_VARIABLES:
            add(required)
        params = longitudinal.spec().get("parameters") or {}
        for key in params.get("strategies") or {}:
            add(key)
    if handle_missing is not None:
        params = handle_missing.spec().get("parameters") or {}
        for key in params.get("strategies") or {}:
            add(key)
        for key in params.get("fill_values") or {}:
            add(key)
    if outlier_handling is not None:
        params = outlier_handling.spec().get("parameters") or {}
        for mapping_name in ("strategies", "tails", "folds"):
            for key in params.get(mapping_name) or {}:
                add(key)
    for creator in new_columns or []:
        for field in collect_filter_fields_from_rules(getattr(creator, "rules", None)):
            add(field)
        for variable in getattr(creator, "cluster_variables", None) or []:
            add(variable)
    for item in algorithm_x or []:
        add(item)
    for item in algorithm_y or []:
        add(item)
    return variables


def collect_filter_fields_from_rules(rules: dict[str, Any] | None) -> set[str]:
    fields: set[str] = set()
    if not rules:
        return fields
    for rule in rules.values():
        if hasattr(rule, "explain"):
            _walk_filter_fields(rule.explain(), fields)
        elif isinstance(rule, dict):
            _walk_filter_fields(rule, fields)
    return fields


def _derived_codes(new_columns: Sequence[Any] | None) -> set[str]:
    codes: set[str] = set()
    for creator in new_columns or []:
        variable = getattr(creator, "variable", None)
        if variable is not None:
            codes.add(code(variable))
    return codes


def build_inputdata(
    *,
    data_model_name: str,
    datasets: Sequence[Any],
    variables: Sequence[str],
    filters: Any = None,
) -> dict[str, Any]:
    filters_payload = None
    if filters is not None:
        filters_payload = filters.to_payload() if hasattr(filters, "to_payload") else filters
    return {
        "data_model": data_model_name,
        "datasets": [code(dataset) for dataset in datasets],
        "validation_datasets": None,
        "filters": filters_payload,
        "variables": list(variables),
    }


def serialize_algorithm_roles(
    x: Sequence[Any] | None,
    y: Sequence[Any] | None,
) -> tuple[list[str] | None, list[str] | None]:
    x_payload = [code(item) for item in x] if x is not None else None
    y_payload = [code(item) for item in y] if y is not None else None
    if x_payload == []:
        x_payload = None
    if y_payload == []:
        y_payload = None
    return x_payload, y_payload


def collect_cluster_variables(new_columns: Iterable[Any] | None) -> list[str]:
    """Cluster source variables required by K-means cluster creators, deduped in order."""
    codes = (
        code(variable)
        for creator in new_columns or []
        for variable in getattr(creator, "cluster_variables", None) or []
    )
    return list(dict.fromkeys(item for item in codes if item))


def effective_missing_handler(handle_missing: Any, new_columns: Iterable[Any] | None) -> Any:
    """User missing-values handler plus a ``drop`` for each K-means cluster variable it does not handle."""
    cluster_variables = collect_cluster_variables(new_columns)
    if not cluster_variables:
        return handle_missing
    strategies = dict(getattr(handle_missing, "_strategies", None) or {})
    handled = {code(key) for key in strategies}
    strategies.update({variable: "drop" for variable in cluster_variables if variable not in handled})
    return MissingValuesHandler(strategies=strategies, fill_values=getattr(handle_missing, "_fill_values", None))


def build_preprocessing_steps(
    *,
    longitudinal: Any = None,
    handle_missing: Any = None,
    outlier_handling: Any = None,
    new_columns: Iterable[Any] | None = None,
) -> list[dict[str, Any]] | None:
    new_columns = list(new_columns or [])
    steps: list[dict[str, Any]] = []
    for step in (longitudinal, effective_missing_handler(handle_missing, new_columns), outlier_handling):
        if step is None:
            continue
        steps.append(step.spec())
    for creator in new_columns:
        steps.append(creator.spec())
    return steps or None


def build_experiment_payload(
    *,
    name: str,
    data_model_name: str,
    datasets: Sequence[Any],
    analysis_set_variables: Sequence[Any],
    filters: Any = None,
    longitudinal: Any = None,
    handle_missing: Any = None,
    outlier_handling: Any = None,
    new_columns: Sequence[Any] | None = None,
    algorithm_name: str,
    algorithm_x: Sequence[Any] | None = None,
    algorithm_y: Sequence[Any] | None = None,
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    x_payload, y_payload = serialize_algorithm_roles(algorithm_x, algorithm_y)
    variables = collect_source_variables(
        analysis_set_variables=analysis_set_variables,
        filters=filters,
        longitudinal=longitudinal,
        handle_missing=handle_missing,
        outlier_handling=outlier_handling,
        new_columns=new_columns,
        algorithm_x=algorithm_x,
        algorithm_y=algorithm_y,
    )
    return {
        "name": name,
        "analysis": {
            "request_id": None,
            "inputdata": build_inputdata(
                data_model_name=data_model_name,
                datasets=datasets,
                variables=variables,
                filters=filters,
            ),
            "preprocessing": build_preprocessing_steps(
                longitudinal=longitudinal,
                handle_missing=handle_missing,
                outlier_handling=outlier_handling,
                new_columns=new_columns,
            ),
            "algorithm": {
                "name": algorithm_name,
                "x": x_payload,
                "y": y_payload,
                "parameters": parameters or {},
            },
            "flags": None,
        },
    }
