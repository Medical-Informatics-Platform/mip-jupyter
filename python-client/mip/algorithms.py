"""Backend algorithm catalog wrappers."""

from __future__ import annotations

from typing import Any
from typing import Mapping

from .display import HelpText
from .labels import normalize_label


class Algorithm:
    """One algorithm specification returned by the backend."""

    def __init__(self, data: Mapping[str, Any]):
        self._data = dict(data or {})
        self._name = self._data.get("name")
        self.label = self._data.get("label") or self._name
        self.description = self._data.get("desc") or self._data.get("description") or ""
        self.type = self._data.get("type")

    def spec(self, client=None) -> dict[str, Any]:
        return dict(self._data)

    def summary(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "description": self.description,
            "type": self.type,
        }


class AlgorithmRegistry:
    """Read-only registry backed by `/algorithms`."""

    def __init__(self, transport):
        self._transport = transport

    def list(self) -> list[Algorithm]:
        payload = self._transport.get("/specifications/algorithms")
        if isinstance(payload, dict):
            payload = payload.get("algorithms") or payload.get("items") or []
        if not isinstance(payload, list):
            return []
        return [Algorithm(item) for item in payload if isinstance(item, dict)]

    def search(self, text: str = "") -> list[Algorithm]:
        needle = normalize_label(text)
        if not needle:
            return self.list()
        return [
            item
            for item in self.list()
            if needle in normalize_label(item.label)
            or needle in normalize_label(item.description)
        ]

    def preprocessing(self) -> list[Algorithm]:
        return self._by_types("preprocessing")

    def statistics(self) -> list[Algorithm]:
        return self._by_types("stat", "statistics")

    def models(self) -> list[Algorithm]:
        return self._by_types("model", "models")

    def _by_types(self, *texts: str) -> list[Algorithm]:
        needles = [text.lower() for text in texts]
        matches = []
        seen = set()
        for item in self.list():
            kind = str(item.type or "").lower()
            if not any(needle in kind for needle in needles):
                continue
            key = item._name or id(item)
            if key in seen:
                continue
            seen.add(key)
            matches.append(item)
        return matches

    def to_frame(self):
        from .display import to_frame

        return to_frame(self.list())

    def help(self) -> HelpText:
        from .display import show_help

        return show_help("AlgorithmRegistry")
