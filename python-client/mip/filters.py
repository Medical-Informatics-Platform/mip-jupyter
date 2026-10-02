"""Filter expression DSL for backend-compatible payloads."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from .exceptions import UnsupportedOperationError
from .labels import internal_code

_OPERATOR_MAP = {
    "==": "equal",
    "!=": "not_equal",
    ">": "greater",
    ">=": "greater_or_equal",
    "<": "less",
    "<=": "less_or_equal",
    "in": "in",
    "not_in": "not_in",
    "is_null": "is_null",
    "is_not_null": "is_not_null",
    "between": "between",
    "not_between": "not_between",
    "contains": "contains",
    "starts_with": "starts_with",
    "ends_with": "ends_with",
}

_NEGATED_OPERATORS = {
    "equal": "not_equal",
    "not_equal": "equal",
    "less": "greater_or_equal",
    "greater": "less_or_equal",
    "less_or_equal": "greater",
    "greater_or_equal": "less",
    "in": "not_in",
    "not_in": "in",
    "is_null": "is_not_null",
    "is_not_null": "is_null",
    "between": "not_between",
    "not_between": "between",
}


@dataclass(frozen=True)
class FilterExpression:
    """Serializable filter expression."""

    payload: dict[str, Any]

    def explain(
        self,
        *,
        lookup: dict[str, str] | None = None,
        enum_lookups: dict[str, dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        payload = _copy_payload(self.payload)
        if lookup is None:
            return payload
        from .labels import sanitize_filter_payload

        return sanitize_filter_payload(payload, lookup, enum_lookups=enum_lookups)

    def to_payload(self) -> dict[str, Any]:
        return _copy_payload(self.payload)

    def __and__(self, other: "FilterExpression") -> "FilterExpression":
        return _combine("AND", self, other)

    def __or__(self, other: "FilterExpression") -> "FilterExpression":
        return _combine("OR", self, other)

    def __invert__(self) -> "FilterExpression":
        return FilterExpression(_negate_payload(self.payload))


def _negate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    copied = _copy_payload(payload)
    if "condition" in copied:
        condition = copied["condition"]
        rules = copied["rules"]
        if condition == "AND":
            return {"condition": "OR", "rules": [_negate_payload(rule) for rule in rules]}
        if condition == "OR":
            return {"condition": "AND", "rules": [_negate_payload(rule) for rule in rules]}
        raise UnsupportedOperationError(f"Filter negation is not supported for condition {condition!r}.")
    operator = copied.get("operator")
    negated = _NEGATED_OPERATORS.get(operator)
    if negated is None:
        raise UnsupportedOperationError(f"Filter negation is not supported for operator {operator!r}.")
    copied["operator"] = negated
    return copied


def _copy_payload(payload: dict[str, Any]) -> dict[str, Any]:
    copied = deepcopy(payload)
    if "rules" in copied:
        copied["rules"] = [dict(item) if isinstance(item, dict) else item for item in copied["rules"]]
    return copied


def _combine(condition: str, left: FilterExpression, right: FilterExpression) -> FilterExpression:
    return FilterExpression({"condition": condition, "rules": [left.to_payload(), right.to_payload()]})


class F:
    """Bound variable used to create filter expressions."""

    def __init__(self, variable: Any):
        self._variable = variable
        self.field = internal_code(variable)

    def __eq__(self, value: Any) -> FilterExpression:  # type: ignore[override]
        return self._rule("==", value)

    def __ne__(self, value: Any) -> FilterExpression:  # type: ignore[override]
        return self._rule("!=", value)

    def __gt__(self, value: Any) -> FilterExpression:
        return self._rule(">", value)

    def __ge__(self, value: Any) -> FilterExpression:
        return self._rule(">=", value)

    def __lt__(self, value: Any) -> FilterExpression:
        return self._rule("<", value)

    def __le__(self, value: Any) -> FilterExpression:
        return self._rule("<=", value)

    def isin(self, values: Any) -> FilterExpression:
        return self._rule("in", list(values))

    def not_in(self, values: Any) -> FilterExpression:
        return self._rule("not_in", list(values))

    def is_null(self) -> FilterExpression:
        return self._rule("is_null", None)

    def is_not_null(self) -> FilterExpression:
        return self._rule("is_not_null", None)

    def between(self, lower: Any, upper: Any) -> FilterExpression:
        return self._rule("between", [lower, upper])

    def not_between(self, lower: Any, upper: Any) -> FilterExpression:
        return self._rule("not_between", [lower, upper])

    def contains(self, value: Any) -> FilterExpression:
        return self._rule("contains", value)

    def starts_with(self, value: Any) -> FilterExpression:
        return self._rule("starts_with", value)

    def ends_with(self, value: Any) -> FilterExpression:
        return self._rule("ends_with", value)

    def _rule(self, operator: str, value: Any) -> FilterExpression:
        return FilterExpression(
            {
                "id": self.field,
                "field": self.field,
                "operator": _OPERATOR_MAP.get(operator, operator),
                "value": self._serialize_value(value),
                "type": _value_type(value),
            }
        )

    def _serialize_value(self, value: Any) -> Any:
        if isinstance(value, (list, tuple)):
            return [self._serialize_scalar(item) for item in value]
        return self._serialize_scalar(value)

    def _serialize_scalar(self, value: Any) -> Any:
        if hasattr(self._variable, "enumeration_code_for"):
            mapped = self._variable.enumeration_code_for(value)
            if mapped is not None:
                return mapped
        return value


def _value_type(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        for item in value:
            if item is not None:
                return _value_type(item)
        return "string"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int) and not isinstance(value, bool):
        return "integer"
    if isinstance(value, float):
        return "double"
    return "string"
