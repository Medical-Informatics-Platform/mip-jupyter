"""Label-first helpers; internal codes are used only for backend payloads."""

from __future__ import annotations

import re
from typing import Any
from typing import Iterable
from typing import Mapping
from typing import Sequence


def normalize_label(text: Any) -> str:
    return str(text or "").strip().casefold()


def slug_from_label(label: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "_", str(label).strip().lower()).strip("_")
    return text or "derived"


def internal_code(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "_code"):
        code = getattr(value, "_code")
        if code is not None:
            return str(code)
    if hasattr(value, "_name"):
        name = getattr(value, "_name")
        if name is not None:
            return str(name)
    if hasattr(value, "code"):
        code = getattr(value, "code")
        if code is not None:
            return str(code)
    return str(value)


def public_label(value: Any) -> str:
    if value is None:
        return ""
    label = getattr(value, "label", None)
    if label is not None and str(label).strip():
        return str(label)
    return str(value)


def enumeration_labels(raw_enums: Any) -> list[str]:
    if isinstance(raw_enums, Mapping):
        labels: list[str] = []
        for key, value in raw_enums.items():
            text = str(value).strip() if value is not None else ""
            labels.append(text or str(key))
        return labels
    if isinstance(raw_enums, (list, tuple)):
        return [str(item) for item in raw_enums]
    return []


def enumeration_code_for_label(raw_enums: Any, label: Any) -> str | None:
    needle = normalize_label(label)
    if isinstance(raw_enums, Mapping):
        for key, value in raw_enums.items():
            if normalize_label(key) == needle:
                return str(key)
            if normalize_label(value) == needle:
                return str(key)
        return None
    if isinstance(raw_enums, (list, tuple)):
        for item in raw_enums:
            if normalize_label(item) == needle:
                return str(item)
    return None


def lookup_by_label(items: Sequence[Any], label: str, *, kind: str = "item") -> Any:
    needle = normalize_label(label)
    matches = [item for item in items if normalize_label(public_label(item)) == needle]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        available = ", ".join(sorted({public_label(item) for item in matches}))
        raise LookupError(f"Ambiguous {kind} label {label!r}. Matches: {available}")
    available = ", ".join(sorted({public_label(item) for item in items}))
    raise KeyError(f"Unknown {kind} label: {label!r}. Available: {available}")


def build_code_to_label_lookup(*collections: Iterable[Any]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for collection in collections:
        for item in collection:
            code = internal_code(item)
            if code:
                lookup[code] = public_label(item)
    return lookup


def build_explain_lookup(
    *,
    data_model: Any,
    datasets: Iterable[Any],
    selected_variables: Iterable[Any],
    data_model_name: str,
) -> dict[str, str]:
    """Label lookup for explain previews; includes full catalog variables when available."""
    dm_variables = getattr(data_model, "variables", None)
    variable_source = dm_variables if dm_variables is not None else selected_variables
    lookup = build_code_to_label_lookup(variable_source, datasets, [data_model])
    lookup[data_model_name] = public_label(data_model)
    return lookup


def _raw_enumerations(variable: Any) -> Any:
    data = getattr(variable, "_data", None)
    if isinstance(data, Mapping):
        return data.get("enumerations") or data.get("enums") or []
    return []


def build_field_enumeration_lookups(variables: Iterable[Any]) -> dict[str, dict[str, str]]:
    """Map variable field code to backend enum code -> human label."""
    lookups: dict[str, dict[str, str]] = {}
    for variable in variables:
        field_code = internal_code(variable)
        if not field_code:
            continue
        raw_enums = _raw_enumerations(variable)
        enum_map: dict[str, str] = {}
        if isinstance(raw_enums, Mapping):
            for key, value in raw_enums.items():
                label = str(value).strip() if value is not None else ""
                enum_map[str(key)] = label or str(key)
        elif isinstance(raw_enums, (list, tuple)):
            for item in raw_enums:
                enum_map[str(item)] = str(item)
        if enum_map:
            lookups[field_code] = enum_map
    return lookups


def sanitize_mapping_keys(mapping: Mapping[Any, Any] | None, lookup: Mapping[str, str]) -> dict[str, Any]:
    if not mapping:
        return {}
    sanitized: dict[str, Any] = {}
    for key, value in mapping.items():
        code = internal_code(key)
        sanitized[lookup.get(code, public_label(key))] = value
    return sanitized


def sanitize_filter_payload(
    payload: Any,
    lookup: Mapping[str, str],
    *,
    enum_lookups: Mapping[str, Mapping[str, str]] | None = None,
) -> Any:
    if not isinstance(payload, dict):
        return payload
    if "condition" in payload:
        return {
            "condition": payload.get("condition"),
            "rules": [
                sanitize_filter_payload(rule, lookup, enum_lookups=enum_lookups)
                for rule in payload.get("rules") or []
            ],
        }
    copied = dict(payload)
    field_code = str(copied.get("field") or copied.get("id") or "")
    enum_map = (enum_lookups or {}).get(field_code, {})
    if field_code in lookup:
        copied["field"] = lookup[field_code]
        copied["id"] = lookup[field_code]
    value = copied.get("value")
    if isinstance(value, list):
        copied["value"] = [_sanitize_filter_value(item, lookup, enum_map) for item in value]
    elif value is not None:
        copied["value"] = _sanitize_filter_value(value, lookup, enum_map)
    return copied


def _sanitize_filter_value(
    value: Any,
    lookup: Mapping[str, str],
    enum_map: Mapping[str, str] | None = None,
) -> Any:
    text = str(value)
    if enum_map and text in enum_map:
        return enum_map[text]
    return lookup.get(text, value)


def _sanitize_preprocessing_dict(step: dict[str, Any], lookup: Mapping[str, str]) -> dict[str, Any]:
    copied = {"name": step.get("name")}
    parameters = dict(step.get("parameters") or {})
    sanitized_parameters: dict[str, Any] = {}
    for key, value in parameters.items():
        if key in {"strategies", "tails", "folds", "fill_values"} and isinstance(value, Mapping):
            sanitized_parameters[key] = sanitize_mapping_keys(value, lookup)
        elif key == "rules" and isinstance(value, Mapping):
            sanitized_parameters[key] = {str(rule_label): rule for rule_label, rule in value.items()}
        elif key == "code":
            continue
        else:
            sanitized_parameters[key] = value
    if sanitized_parameters:
        copied["parameters"] = sanitized_parameters
    return copied


def sanitize_explain_dict(
    payload: dict[str, Any],
    *,
    lookup: Mapping[str, str],
    enum_lookups: Mapping[str, Mapping[str, str]] | None = None,
) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in payload.items():
        if key == "analysis_set" and isinstance(value, dict):
            sanitized[key] = {
                "data_model": value.get("data_model"),
                "datasets": list(value.get("datasets") or []),
                "variables": list(value.get("variables") or []),
            }
        elif key == "filters":
            sanitized[key] = sanitize_filter_payload(value, lookup, enum_lookups=enum_lookups)
        elif key == "preprocessing":
            if isinstance(value, list):
                sanitized[key] = [_sanitize_preprocessing_dict(item, lookup) for item in value]
            else:
                sanitized[key] = value
        else:
            sanitized[key] = value
    return sanitized


def sanitize_inputdata(
    payload: dict[str, Any],
    *,
    lookup: Mapping[str, str],
    enum_lookups: Mapping[str, Mapping[str, str]] | None = None,
) -> dict[str, Any]:
    datasets = payload.get("datasets") or []
    variables = payload.get("variables") or []
    raw_model = payload.get("data_model")
    return {
        "data_model": lookup.get(str(raw_model), public_label(raw_model) if raw_model else raw_model),
        "datasets": [lookup.get(str(item), str(item)) for item in datasets],
        "validation_datasets": payload.get("validation_datasets"),
        "filters": sanitize_filter_payload(payload.get("filters"), lookup, enum_lookups=enum_lookups),
        "variables": [lookup.get(str(item), str(item)) for item in variables],
    }


def list_group_summaries(groups: Iterable[Any]) -> list[dict[str, Any]]:
    from .metadata_tree import list_groups

    return [
        {"label": item.get("label") or item.get("path", [""])[-1], "path": item.get("path") or []}
        for item in list_groups(groups)
        if item.get("label") or item.get("path")
    ]
