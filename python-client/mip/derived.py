"""Derived variables created by preprocessing steps."""

from __future__ import annotations

from typing import Any

from .labels import slug_from_label


class DerivedVariable:
    """A categorical variable created by preprocessing, not from the catalog."""

    def __init__(
        self,
        *,
        label: str,
        enumerations: list[str] | None = None,
        created_by: str | None = None,
        _code: str | None = None,
    ):
        self.label = label
        self._code = _code or slug_from_label(label)
        self._enumerations = list(enumerations or [])
        self.created_by = created_by

    def __repr__(self) -> str:
        return f"<DerivedVariable(label={self.label!r})>"

    def details(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "categorical": True,
            "numerical": False,
            "categories": self.categories(),
            "derived": True,
        }

    def is_numerical(self) -> bool:
        return False

    def is_categorical(self) -> bool:
        return True

    def categories(self) -> list[str]:
        return list(self._enumerations)

    def summary(self) -> dict[str, Any]:
        return self.details()
