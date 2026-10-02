"""Analysis set selection and simple exploration helpers."""

from __future__ import annotations

from typing import Any
from typing import Sequence

from .exceptions import MipConfigurationError
from .display import HelpText
from .labels import build_explain_lookup
from .labels import build_field_enumeration_lookups
from .labels import public_label
from .labels import sanitize_inputdata
from .request_builder import build_inputdata
from .request_builder import code as _code
from .results import Result


class AnalysisSet:
    """Selected data model, datasets, and variables for analysis."""

    def __init__(self, *, data_model: Any, datasets: Sequence[Any], variables: Sequence[Any]):
        self.data_model = data_model
        self.datasets = list(datasets or [])
        self.variables = list(variables or [])
        self._transport = getattr(data_model, "_transport", None)

    def data_model_name(self) -> str:
        return _data_model_name(self.data_model)

    def _lookup(self) -> dict[str, str]:
        return build_explain_lookup(
            data_model=self.data_model,
            datasets=self.datasets,
            selected_variables=self.variables,
            data_model_name=self.data_model_name(),
        )

    def _enum_lookups(self) -> dict[str, dict[str, str]]:
        dm_variables = getattr(self.data_model, "variables", None)
        if dm_variables is not None:
            return build_field_enumeration_lookups(dm_variables)
        return build_field_enumeration_lookups(self.variables)

    def inputdata(self, *, filters=None, extra_variables: Sequence[Any] | None = None) -> dict:
        variables = [_code(variable) for variable in self.variables]
        if extra_variables:
            seen = set(variables)
            for variable in extra_variables:
                item = _code(variable)
                if item and item not in seen:
                    seen.add(item)
                    variables.append(item)
        return build_inputdata(
            data_model_name=self.data_model_name(),
            datasets=self.datasets,
            variables=variables,
            filters=filters,
        )

    def histogram(self, variable: Any, bins: int | None = None, mode: str = "transient") -> Result:
        from .pipeline import Pipeline

        return Pipeline(analysis_set=self).histogram(variable=variable, bins=bins, mode=mode)

    def summary(self) -> dict[str, Any]:
        return {
            "data_model": public_label(self.data_model),
            "datasets": [public_label(dataset) for dataset in self.datasets],
            "variables": [public_label(variable) for variable in self.variables],
        }

    def explain(self) -> dict[str, Any]:
        return sanitize_inputdata(
            self.inputdata(),
            lookup=self._lookup(),
            enum_lookups=self._enum_lookups(),
        )

    def _repr_html_(self) -> str:
        from .display import render_object_card

        summary = self.summary()
        return render_object_card(
            "AnalysisSet",
            {
                "data_model": summary["data_model"],
                "datasets": ", ".join(summary["datasets"]),
                "variables": ", ".join(summary["variables"]),
            },
            [".summary()", ".explain()", ".help()"],
        )

    def help(self) -> HelpText:
        from .display import show_help

        return show_help("AnalysisSet")

    def _require_transport(self):
        if self._transport is None:
            raise MipConfigurationError(
                "This AnalysisSet is not attached to a Client-created DataModel and cannot execute algorithms."
            )
        return self._transport


def _data_model_name(data_model: Any) -> str:
    if hasattr(data_model, "internal_name"):
        return data_model.internal_name()
    return _code(data_model)
