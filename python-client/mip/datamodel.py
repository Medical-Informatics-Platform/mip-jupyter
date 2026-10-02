"""Data-model objects built from backend DTOs."""

from __future__ import annotations

from typing import Any
from typing import Mapping
from typing import Sequence

from .datasets import Dataset
from .datasets import DatasetCollection
from .display import HelpText
from .labels import list_group_summaries
from .labels import normalize_label
from .variables import Variable
from .variables import VariableCollection


class DataModel:
    """Backend data-model metadata with variable and dataset collections."""

    def __init__(self, data: Mapping[str, Any], *, transport=None):
        self._transport = transport
        self._data = dict(data or {})
        self._code = self._data.get("code")
        self.version = self._data.get("version")
        self.label = self._data.get("label") or self._code
        self.longitudinal = self._data.get("longitudinal")
        self.groups = list(self._data.get("groups") or [])
        self.datasets_variables = dict(
            self._data.get("datasetsVariables") or self._data.get("datasets_variables") or {}
        )
        self.variables = VariableCollection(
            _flatten_variables(self._data),
            groups=self.groups,
            root_variables=self.root_variables(),
        )
        self.datasets = DatasetCollection(self._data.get("datasets") or [], data_model=self)

    def __repr__(self) -> str:
        return f"<DataModel(label={self.label!r}, version={self.version!r})>"

    def _repr_html_(self) -> str:
        from .display import render_object_card

        return render_object_card(
            f"DataModel: {self.name}",
            {
                "label": self.label,
                "version": self.version,
                "n_datasets": len(self.datasets),
                "n_variables": len(self.variables),
            },
            [
                ".summary()",
                ".select(datasets=[...], variables=[...])",
                ".browse()",
                ".datasets.list()",
                ".variables.search(\"Age\")",
                ".tree()",
                ".help()",
            ],
        )

    def help(self) -> HelpText:
        from .display import show_help

        return show_help("DataModel")

    def browse(self, *, max_variable_options: int = 200):
        """Interactive dataset/variable picker (requires ipywidgets)."""
        from .widgets import browse_analysis_set

        return browse_analysis_set(self, max_variable_options=max_variable_options)

    def select(
        self,
        *,
        datasets: Sequence[Any],
        variables: Sequence[Any],
    ):
        """Build an AnalysisSet from dataset/variable labels or objects."""
        from .analysis import AnalysisSet

        if not datasets:
            raise ValueError("select() requires at least one dataset.")
        if not variables:
            raise ValueError("select() requires at least one variable.")

        return AnalysisSet(
            data_model=self,
            datasets=[_resolve_dataset(self, item) for item in datasets],
            variables=[_resolve_variable(self, item) for item in variables],
        )

    @property
    def name(self) -> str:
        if self.version:
            return f"{self.label} ({self.version})"
        return str(self.label or "")

    def internal_name(self) -> str:
        if self._code and self.version:
            return f"{self._code}:{self.version}"
        return str(self._code or self.version or "")

    def details(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "version": self.version,
            "longitudinal": self.longitudinal,
            "n_variables": len(self.variables),
            "n_datasets": len(self.datasets),
        }

    def summary(self) -> dict[str, Any]:
        return self.details()

    def root_variables(self) -> list[dict[str, Any]]:
        return [dict(item) for item in (self._data.get("variables") or []) if isinstance(item, Mapping)]

    def list_datasets(self) -> list[dict[str, Any]]:
        return [dataset.summary() for dataset in self.datasets.to_list()]

    def list_variables(self) -> list[dict[str, Any]]:
        return [variable.summary() for variable in self.variables.to_list()]

    def list_groups(self) -> list[dict[str, Any]]:
        return list_group_summaries(self.groups)

    def tree(self, *, group: Any | None = None, include_variables: bool = False, max_lines: int = 250):
        from .metadata_tree import MetadataTree
        from .metadata_tree import find_group
        from .metadata_tree import list_groups
        from .metadata_tree import pathology_from_data_model
        from .metadata_tree import render_pathology_tree
        from .metadata_tree import render_pathology_tree_html

        focus_group = None
        focus_group_path = None
        if group is not None:
            match = find_group(self.groups, group)
            if match is None:
                available = ", ".join(
                    sorted(
                        {
                            str(item.get("label") or item.get("path", [""])[-1])
                            for item in list_groups(self.groups)
                            if item.get("label") or item.get("path")
                        }
                    )
                )
                raise LookupError(f"Unknown group {group!r}. Available groups: {available}")
            focus_group, focus_group_path = match

        pathology = pathology_from_data_model(self)
        return MetadataTree(
            render_pathology_tree(
                pathology,
                include_variables=include_variables,
                max_lines=max_lines,
                focus_group=focus_group,
                focus_group_path=focus_group_path,
            ),
            html=render_pathology_tree_html(
                pathology,
                include_variables=include_variables,
                max_nodes=max_lines,
                focus_group=focus_group,
                focus_group_path=focus_group_path,
            ),
        )


def _flatten_variables(data: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    items: list[Mapping[str, Any]] = []
    seen: set[str] = set()

    def add(variable: Any) -> None:
        if not isinstance(variable, Mapping):
            return
        code = variable.get("code")
        if code is None or code in seen:
            return
        seen.add(code)
        items.append(variable)

    def visit_group(group: Any) -> None:
        if not isinstance(group, Mapping):
            return
        for variable in group.get("variables") or []:
            add(variable)
        for child in group.get("groups") or []:
            visit_group(child)

    for variable in data.get("variables") or []:
        add(variable)
    for group in data.get("groups") or []:
        visit_group(group)
    return items


def _resolve_dataset(model: DataModel, item: Any) -> Dataset:
    if isinstance(item, Dataset):
        return item
    return model.datasets[str(item)]


def _resolve_variable(model: DataModel, item: Any) -> Variable:
    if isinstance(item, Variable):
        return item
    return model.variables[str(item)]
