"""Compact, token-cheap helpers for AI agents: the bundled guide and metadata summaries.

Shared by the `mip` command line and the hosted notebook's Jupyter MCP tools.
Every result is a small JSON-able dict; nothing here prints or returns secrets.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

DOCS_ROOT = Path(__file__).resolve().parent / "agent_docs"

# Page key -> path under the docs root (the folder holding INDEX.md and wiki/).
GUIDE_PAGES: dict[str, str] = {
    "index": "INDEX.md",
    "00-agent-workspace": "wiki/00-agent-workspace.md",
    "01-onboarding": "wiki/01-onboarding.md",
    "02-analysis-workflow": "wiki/02-analysis-workflow.md",
    "03-mip-client-api": "wiki/03-mip-client-api.md",
    "04-jupyter-mcp": "wiki/04-jupyter-mcp.md",
    "05-env-and-backend": "wiki/05-env-and-backend.md",
    "06-runtime-state": "wiki/06-runtime-state.md",
    "07-pipeline-algorithms": "wiki/07-pipeline-algorithms.md",
    "agent-exploration": "wiki/agent-exploration.md",
    "dev-contributor": "wiki/dev-contributor.md",
    "recipes/stroke-analysis": "wiki/recipes/stroke-analysis.md",
}
DEFAULT_GUIDE_PAGE = "00-agent-workspace"

DEFAULT_WIKI_MAX_CHARS = 3000
MAX_WIKI_CONTENT_CHARS = 6000
MAX_DOC_RESULTS = 10
MAX_DOC_SNIPPET_CHARS = 600
MAX_LIST_ITEMS = 40
DEFAULT_CATALOG_LIMIT = 10
DEFAULT_VARIABLE_SEARCH_LIMIT = 10
DEFAULT_ALGORITHM_SUMMARY_LIMIT = 20
DEFAULT_DATA_MODEL_LIST_LIMIT = 20
MAX_METADATA_ITEM_CHARS = 400
MAX_METADATA_STRING_CHARS = 180
MAX_RESPONSE_JSON_CHARS = 12000


def clamp(value: int | str | None, default: int, maximum: int) -> int:
    if value is None:
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(parsed, maximum))


def truncate(text: Any, max_chars: int, *, suffix: str = "...") -> str:
    value = str(text or "")
    if len(value) <= max_chars:
        return value
    if max_chars <= len(suffix):
        return value[:max_chars]
    return value[: max_chars - len(suffix)] + suffix


def markdown_title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def snippet_for_query(text: str, query: str) -> str:
    lower_text = text.lower()
    terms = [term for term in re.split(r"\W+", query.lower()) if term]
    positions = [lower_text.find(term) for term in terms if lower_text.find(term) >= 0]
    start = max(0, min(positions) - 120) if positions else 0
    snippet = text[start : start + MAX_DOC_SNIPPET_CHARS].strip()
    return truncate(snippet.replace("\r\n", "\n"), MAX_DOC_SNIPPET_CHARS)


def _section_matches(text: str, topic: str | None) -> list[str]:
    terms = [term for term in re.split(r"\W+", (topic or "").lower()) if term]
    if not terms:
        return [text]
    sections: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        if line.startswith("#") and current:
            section = "\n".join(current).strip()
            if any(term in section.lower() for term in terms):
                sections.append(section)
            current = [line]
        else:
            current.append(line)
    if current:
        section = "\n".join(current).strip()
        if any(term in section.lower() for term in terms):
            sections.append(section)
    return sections


def guide_page_key(page: str | None) -> str:
    key = str(page or DEFAULT_GUIDE_PAGE).strip().replace("\\", "/")
    key = key.removesuffix(".md").removeprefix("wiki/")
    if key not in GUIDE_PAGES:
        allowed = ", ".join(sorted(GUIDE_PAGES))
        raise ValueError(f"Unknown guide page {page!r}; allowed pages: {allowed}")
    return key


def read_guide(
    page: str | None = None,
    topic: str | None = None,
    max_chars: int = DEFAULT_WIKI_MAX_CHARS,
    *,
    docs_root: Path | None = None,
) -> dict[str, Any]:
    """Read one allowlisted guide page, optionally narrowed to sections matching `topic`."""

    page_key = guide_page_key(page)
    relative_path = GUIDE_PAGES[page_key]
    path = (docs_root or DOCS_ROOT) / relative_path
    max_chars = clamp(max_chars, DEFAULT_WIKI_MAX_CHARS, MAX_WIKI_CONTENT_CHARS)
    if not path.is_file():
        return {"ok": False, "page": page_key, "path": relative_path, "error": "Agent wiki page is missing."}
    text = path.read_text(encoding="utf-8")
    # A missed topic falls back to the whole page and reports matched=false.
    sections = _section_matches(text, topic)
    content = "\n\n".join(sections) if sections else text
    return {
        "ok": True,
        "page": page_key,
        "path": relative_path,
        "topic": topic,
        "matched": bool(sections),
        "content": truncate(content, max_chars),
        "truncated": len(content) > max_chars,
    }


def _read_when(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("**Read when:**"):
            return line[len("**Read when:**"):].strip()
    return ""


def list_guide_pages(*, docs_root: Path | None = None) -> dict[str, Any]:
    """List guide pages with their title and one-line "Read when" hint."""

    root = docs_root or DOCS_ROOT
    pages = []
    for key, relative_path in GUIDE_PAGES.items():
        path = root / relative_path
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        pages.append({"page": key, "title": markdown_title(text, key), "read_when": _read_when(text)})
    return {"ok": True, "count": len(pages), "pages": pages}


def search_guide(query: str, limit: int = 5, *, docs_root: Path | None = None) -> dict[str, Any]:
    """Search the guide pages and return bounded snippets, best match first."""

    query = str(query or "").strip()
    if not query:
        raise ValueError("query is required.")
    limit = clamp(limit, 5, MAX_DOC_RESULTS)
    terms = [term for term in re.split(r"\W+", query.lower()) if term]
    root = docs_root or DOCS_ROOT
    results: list[dict[str, Any]] = []
    for key, relative_path in GUIDE_PAGES.items():
        path = root / relative_path
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        score = sum(text.lower().count(term) for term in terms)
        if score > 0:
            results.append(
                {
                    "page": key,
                    "title": markdown_title(text, key),
                    "score": score,
                    "snippet": snippet_for_query(text, query),
                }
            )
    results.sort(key=lambda item: (-int(item["score"]), str(item["page"])))
    return {"ok": True, "query": query, "count": len(results), "results": results[:limit]}


def env_status(token_dir: Path | None = None) -> dict[str, Any]:
    """Report whether the MIP connection is configured; never returns values or env names."""

    def configured(*names: str) -> bool:
        return any(os.getenv(name) for name in names)

    remote = configured("MIP_URL")
    backend_configured = configured("PLATFORM_BACKEND_URL", "MIP_BASE_URL") or remote
    token_configured = configured("PLATFORM_TOKEN", "MIP_TOKEN")
    # In the hosted notebook, and from your own computer, the hub hands the token out on first use.
    token_configured = token_configured or (
        (configured("JUPYTERHUB_API_URL") or remote) and configured("JUPYTERHUB_API_TOKEN", "MIP_API_TOKEN")
    )
    if not token_configured:
        folder = token_dir or Path.cwd()
        token_configured = any(
            token_file.is_file() and token_file.stat().st_size > 0
            for token_file in (folder / "mip_token", folder / ".mip_token")
        )
    return {
        "ok": True,
        "connection_configured": bool(backend_configured),
        "authenticated": bool(token_configured),
        "ready": bool(backend_configured and token_configured),
    }


def _client():
    from mip import Client

    return Client.from_env()


def _tool_error(exc: Exception) -> dict[str, Any]:
    return {
        "ok": False,
        "error_type": type(exc).__name__,
        "error": truncate(str(exc), MAX_METADATA_STRING_CHARS),
    }


_METADATA_PRIORITY = (
    "code",
    "id",
    "slug",
    "name",
    "label",
    "type",
    "version",
    "desc",
    "description",
    "n_variables",
    "n_datasets",
    "n_groups",
    "n_rows",
)


def _compact_metadata_item(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {"value": truncate(item, MAX_METADATA_ITEM_CHARS)}

    compact: dict[str, Any] = {}
    for key in _METADATA_PRIORITY:
        if key not in item:
            continue
        value = item[key]
        if isinstance(value, str):
            compact[key] = truncate(value, MAX_METADATA_STRING_CHARS)
        elif value is None or isinstance(value, (bool, int, float)):
            compact[key] = value

    if len(json.dumps(compact, ensure_ascii=False)) <= MAX_METADATA_ITEM_CHARS:
        return compact

    fitted: dict[str, Any] = {}
    for key in _METADATA_PRIORITY:
        if key not in compact:
            continue
        candidate = {**fitted, key: compact[key]}
        if len(json.dumps(candidate, ensure_ascii=False)) <= MAX_METADATA_ITEM_CHARS:
            fitted = candidate
    return fitted


def _compact_metadata_items(items: list[Any], limit: int) -> list[dict[str, Any]]:
    return [_compact_metadata_item(item) for item in items[:limit]]


def bounded_response(payload: dict[str, Any], *, list_keys: tuple[str, ...]) -> dict[str, Any]:
    payload["response_truncated"] = False
    while len(json.dumps(payload, ensure_ascii=False)) > MAX_RESPONSE_JSON_CHARS:
        candidates = [key for key in list_keys if payload.get(key)]
        if not candidates:
            break
        key = max(candidates, key=lambda candidate: len(payload[candidate]))
        payload[key].pop()
        payload["response_truncated"] = True
    return payload


def catalog_summary(limit: int = DEFAULT_CATALOG_LIMIT) -> dict[str, Any]:
    """Return compact summaries of the data models you are allowed to see."""

    limit = clamp(limit, DEFAULT_CATALOG_LIMIT, MAX_LIST_ITEMS)
    try:
        summaries = _client().catalog().summaries()
    except Exception as exc:  # noqa: BLE001 - agents get structured errors, not tracebacks.
        return _tool_error(exc)
    return bounded_response(
        {
            "ok": True,
            "count": len(summaries),
            "items": _compact_metadata_items(summaries, limit),
            "truncated": len(summaries) > limit,
        },
        list_keys=("items",),
    )


def data_model_summary(
    code: str,
    version: str | None = None,
    include_variables: bool = False,
    include_groups: bool = False,
    limit: int = DEFAULT_DATA_MODEL_LIST_LIMIT,
) -> dict[str, Any]:
    """Return compact metadata for one data model."""

    limit = clamp(limit, DEFAULT_DATA_MODEL_LIST_LIMIT, MAX_LIST_ITEMS)
    try:
        data_model = _client().catalog().data_model(code, version=version)
        variables = data_model.list_variables() if include_variables else []
        groups = data_model.list_groups() if include_groups else []
        datasets = data_model.list_datasets()
    except Exception as exc:  # noqa: BLE001 - agents get structured errors, not tracebacks.
        return _tool_error(exc)

    return bounded_response(
        {
            "ok": True,
            "summary": _compact_metadata_item(data_model.summary()),
            "datasets": _compact_metadata_items(datasets, limit),
            "datasets_truncated": len(datasets) > limit,
            "groups": _compact_metadata_items(groups, limit),
            "groups_truncated": len(groups) > limit,
            "variables": _compact_metadata_items(variables, limit),
            "variables_truncated": len(variables) > limit,
        },
        list_keys=("datasets", "groups", "variables"),
    )


def search_variables(
    code: str,
    query: str,
    version: str | None = None,
    limit: int = DEFAULT_VARIABLE_SEARCH_LIMIT,
) -> dict[str, Any]:
    """Search variables in one data model by code or label."""

    limit = clamp(limit, DEFAULT_VARIABLE_SEARCH_LIMIT, MAX_LIST_ITEMS)
    try:
        data_model = _client().catalog().data_model(code, version=version)
        matches = [variable.summary() for variable in data_model.variables.search(query)]
    except Exception as exc:  # noqa: BLE001 - agents get structured errors, not tracebacks.
        return _tool_error(exc)
    return bounded_response(
        {
            "ok": True,
            "code": code,
            "version": version,
            "query": query,
            "count": len(matches),
            "items": _compact_metadata_items(matches, limit),
            "truncated": len(matches) > limit,
        },
        list_keys=("items",),
    )


def algorithm_summary(limit: int = DEFAULT_ALGORITHM_SUMMARY_LIMIT) -> dict[str, Any]:
    """Return compact summaries of the available algorithms."""

    limit = clamp(limit, DEFAULT_ALGORITHM_SUMMARY_LIMIT, MAX_LIST_ITEMS)
    try:
        summaries = [algorithm.summary() for algorithm in _client().algorithms().list()]
    except Exception as exc:  # noqa: BLE001 - agents get structured errors, not tracebacks.
        return _tool_error(exc)

    counts_by_type: dict[str, int] = {}
    for item in summaries:
        kind = str(item.get("type") or "unknown")
        counts_by_type[kind] = counts_by_type.get(kind, 0) + 1
    return bounded_response(
        {
            "ok": True,
            "count": len(summaries),
            "counts_by_type": counts_by_type,
            "items": _compact_metadata_items(summaries, limit),
            "truncated": len(summaries) > limit,
        },
        list_keys=("items",),
    )
