"""Dataset wrappers for backend data-model metadata."""

from __future__ import annotations

from typing import Any
from typing import Iterable
from typing import Mapping

from .display import HelpText
from .labels import lookup_by_label
from .labels import normalize_label
from .variables import Variable


class Dataset:
    """One dataset entry from a backend data model."""

    def __init__(self, data: Mapping[str, Any], *, data_model: Any | None = None):
        self._data = dict(data or {})
        self._data_model = data_model
        self._code = self._data.get("code")
        self.label = self._data.get("label") or self._code

    def __repr__(self) -> str:
        return f"<Dataset(label={self.label!r})>"

    def _repr_html_(self) -> str:
        from .display import render_object_card

        variables = self.variables()
        preview = ", ".join(variable.label for variable in variables[:6] if variable.label)
        if len(variables) > 6:
            preview += f", … (+{len(variables) - 6})"
        fields: dict[str, Any] = {
            "label": self.label,
            "n_variables": len(variables),
        }
        if preview:
            fields["variables"] = preview
        return render_object_card(
            f"Dataset: {self.label}",
            fields,
            [".summary()", ".details()", ".variables()", ".help()"],
        )

    def help(self) -> HelpText:
        from .display import show_help

        return show_help("Dataset")

    def details(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "n_variables": len(self.variables()),
        }

    def variables(self) -> list[Variable]:
        if self._data_model is None:
            return []
        allowed = set((self._data_model.datasets_variables or {}).get(self._code, []) or [])
        if not allowed:
            return self._data_model.variables.to_list()
        return [variable for variable in self._data_model.variables if variable._code in allowed]

    def has_variable(self, variable: Variable | str) -> bool:
        if isinstance(variable, Variable):
            target = variable._code
        else:
            try:
                target = self._data_model.variables[str(variable)]._code
            except Exception:
                target = str(variable)
        return any(item._code == target for item in self.variables())

    def summary(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "n_variables": len(self.variables()),
        }


class DatasetCollection:
    """Indexable collection of datasets for a data model."""

    def __init__(self, datasets: Iterable[Dataset | Mapping[str, Any]], *, data_model: Any | None = None):
        self._items = [
            item if isinstance(item, Dataset) else Dataset(item, data_model=data_model)
            for item in datasets
        ]
        self._by_code = {item._code: item for item in self._items if item._code is not None}

    def __iter__(self):
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __getitem__(self, label: str) -> Dataset:
        return lookup_by_label(self._items, label, kind="dataset")

    def search(self, text: str = "") -> list[Dataset]:
        needle = normalize_label(text)
        if not needle:
            return self.to_list()
        return [item for item in self._items if needle in normalize_label(item.label)]

    def to_list(self) -> list[Dataset]:
        return list(self._items)

    def list(self) -> list[Dataset]:
        """Return all datasets as a list."""
        return self.to_list()

    def to_frame(self):
        from .display import to_frame

        return to_frame(self._items)

    def help(self) -> HelpText:
        from .display import show_help

        return show_help("DatasetCollection")
