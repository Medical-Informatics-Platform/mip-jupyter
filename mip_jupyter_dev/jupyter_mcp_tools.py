"""Curated, production-safe Jupyter MCP tools for mip-jupyter."""

from __future__ import annotations

import json
import os
import re
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any
from typing import Literal


GUIDE_RELATIVE_PATH = Path("llm") / "wiki" / "00-agent-workspace.md"
ALLOWED_WIKI_PAGES: dict[str, Path] = {
    "index": Path("llm") / "INDEX.md",
    "00-agent-workspace": GUIDE_RELATIVE_PATH,
    "01-onboarding": Path("llm") / "wiki" / "01-onboarding.md",
    "02-analysis-workflow": Path("llm") / "wiki" / "02-analysis-workflow.md",
    "03-mip-client-api": Path("llm") / "wiki" / "03-mip-client-api.md",
    "04-jupyter-mcp": Path("llm") / "wiki" / "04-jupyter-mcp.md",
    "05-env-and-backend": Path("llm") / "wiki" / "05-env-and-backend.md",
    "06-runtime-state": Path("llm") / "wiki" / "06-runtime-state.md",
    "07-pipeline-algorithms": Path("llm") / "wiki" / "07-pipeline-algorithms.md",
    "agent-exploration": Path("llm") / "wiki" / "agent-exploration.md",
    "dev-contributor": Path("llm") / "wiki" / "dev-contributor.md",
    "recipes/stroke-analysis": Path("llm") / "wiki" / "recipes" / "stroke-analysis.md",
}
BLOCKED_PATH_PARTS = {".ipynb_checkpoints", ".venv", ".playwright-cli", "__pycache__"}
MAX_DOC_RESULTS = 10
MAX_DOC_SNIPPET_CHARS = 600
MAX_WIKI_CONTENT_CHARS = 6000
DEFAULT_WIKI_MAX_CHARS = 3000
MAX_CELL_READ_CHARS = 20000
MAX_CELL_WRITE_CHARS = 4000
MAX_SCRATCH_PAYLOAD_CHARS = 8000
MAX_SCRATCH_SNIPPET_CHARS = 1024
SCRATCH_TEMPLATE_DEFAULT = "examples/algorithm_examples.py"
MAX_SCRATCH_READ_CHARS = 8000
MAX_SCRATCH_LIST_ITEMS = 50
MAX_NOTEBOOK_OUTLINE_CELLS = 100
MAX_EXECUTED_CELL_SUMMARIES = 20
# Hard caps for MIP metadata list payloads (production Cohort Scout context).
MAX_LIST_ITEMS = 40
DEFAULT_CATALOG_LIMIT = 10
DEFAULT_VARIABLE_SEARCH_LIMIT = 10
DEFAULT_ALGORITHM_SUMMARY_LIMIT = 20
DEFAULT_DATA_MODEL_LIST_LIMIT = 20
MAX_METADATA_ITEM_CHARS = 400
MAX_METADATA_STRING_CHARS = 180
MAX_RESPONSE_JSON_CHARS = 12000
SAFE_JUPYTER_MCP_TOOLS = [
    "mip_jupyter_dev.jupyter_mcp_tools:agent_read_guide",
    "mip_jupyter_dev.jupyter_mcp_tools:agent_search_docs",
    "mip_jupyter_dev.jupyter_mcp_tools:notebook_outline",
    "mip_jupyter_dev.jupyter_mcp_tools:notebook_read_cell",
    "mip_jupyter_dev.jupyter_mcp_tools:create_notebook",
    "mip_jupyter_dev.jupyter_mcp_tools:append_markdown_cell",
    "mip_jupyter_dev.jupyter_mcp_tools:append_code_cell",
    "mip_jupyter_dev.jupyter_mcp_tools:edit_cell_by_index",
    "mip_jupyter_dev.jupyter_mcp_tools:run_cell_by_index",
    "mip_jupyter_dev.jupyter_mcp_tools:run_all_cells",
    "mip_jupyter_dev.jupyter_mcp_tools:open_file",
    "mip_jupyter_dev.jupyter_mcp_tools:mip_env_status",
    "mip_jupyter_dev.jupyter_mcp_tools:mip_catalog_summary",
    "mip_jupyter_dev.jupyter_mcp_tools:mip_data_model_summary",
    "mip_jupyter_dev.jupyter_mcp_tools:mip_search_variables",
    "mip_jupyter_dev.jupyter_mcp_tools:mip_algorithm_summary",
    "mip_jupyter_dev.jupyter_mcp_tools:scratch_copy_template",
    "mip_jupyter_dev.jupyter_mcp_tools:scratch_read",
    "mip_jupyter_dev.jupyter_mcp_tools:scratch_append_lines",
    "mip_jupyter_dev.jupyter_mcp_tools:scratch_write_file",
    "mip_jupyter_dev.jupyter_mcp_tools:scratch_replace_snippet",
    "mip_jupyter_dev.jupyter_mcp_tools:scratch_to_notebook",
    "mip_jupyter_dev.jupyter_mcp_tools:scratch_list",
]


def _workspace_root() -> Path:
    configured = os.getenv("MIP_JUPYTER_ROOT")
    if configured:
        path = Path(configured).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        return path.resolve()

    cwd = Path.cwd().resolve()
    local_workspace = cwd / "workspace"
    if local_workspace.is_dir():
        return local_workspace.resolve()
    return cwd


def _strip_workspace_prefix(path: str) -> str:
    parsed = PurePosixPath(path.replace("\\", "/"))
    if parsed.is_absolute():
        return path
    parts = parsed.parts
    if parts and parts[0] == "workspace":
        return PurePosixPath(*parts[1:]).as_posix()
    return parsed.as_posix()


def _require_within_workspace(path: Path) -> None:
    root = _workspace_root()
    try:
        path.resolve().relative_to(root)
    except ValueError as exc:
        raise ValueError("Path must stay under the Jupyter workspace.") from exc


def _workspace_relative_path(path: str) -> Path:
    raw = str(path or "").strip()
    if not raw:
        raise ValueError("Path is required.")

    normalized = _strip_workspace_prefix(raw)
    parsed = PurePosixPath(normalized.replace("\\", "/"))
    if parsed.is_absolute():
        candidate = Path(normalized).expanduser().resolve()
        _require_within_workspace(candidate)
        relative = candidate.relative_to(_workspace_root())
    else:
        if any(part == ".." for part in parsed.parts):
            raise ValueError("Path must not contain '..'.")
        if any(part in BLOCKED_PATH_PARTS for part in parsed.parts):
            raise ValueError("Path points to a blocked workspace location.")
        relative = Path(*parsed.parts)
        candidate = (_workspace_root() / relative).resolve()
        _require_within_workspace(candidate)
    return relative


def _workspace_file(path: str) -> tuple[Path, Path]:
    relative = _workspace_relative_path(path)
    return relative, _workspace_root() / relative


def _server_path(relative_path: Path) -> str:
    """Return the Jupyter-server-visible path for local dev or production roots."""

    root = _workspace_root()
    cwd = Path.cwd().resolve()
    try:
        root_prefix = root.relative_to(cwd)
    except ValueError:
        root_prefix = Path()
    if str(root_prefix) in {"", "."}:
        return relative_path.as_posix()
    return (root_prefix / relative_path).as_posix()


def _limit(value: int | str | None, default: int, maximum: int) -> int:
    if value is None:
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(parsed, maximum))


def _validate_cell_content(content: str, *, label: str = "content") -> None:
    if len(content) > MAX_CELL_WRITE_CHARS:
        raise ValueError(
            f"{label} exceeds {MAX_CELL_WRITE_CHARS} characters; "
            "split into smaller scratch-append-lines or append-code calls."
        )


def _truncate(text: Any, max_chars: int, *, suffix: str = "...") -> str:
    value = str(text or "")
    if len(value) <= max_chars:
        return value
    if max_chars <= len(suffix):
        return value[:max_chars]
    return value[: max_chars - len(suffix)] + suffix


def _cell_source(cell: dict[str, Any]) -> str:
    source = cell.get("source", "")
    if isinstance(source, list):
        return "".join(str(item) for item in source)
    return str(source or "")


def _source_preview(source: str, max_chars: int = 240) -> str:
    lines = [line.rstrip() for line in source.strip().splitlines()]
    preview = "\n".join(lines[:8])
    return _truncate(preview, max_chars)


def _markdown_headings(source: str) -> list[str]:
    headings: list[str] = []
    for line in source.splitlines():
        match = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*$", line)
        if match:
            headings.append(match.group(1).strip())
        if len(headings) >= 5:
            break
    return headings


def _output_summary(outputs: list[dict[str, Any]], *, max_outputs: int = 5) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for output in outputs[:max_outputs]:
        output_type = output.get("output_type")
        item: dict[str, Any] = {"output_type": output_type}
        if output_type == "error":
            item["ename"] = output.get("ename")
            item["evalue"] = _truncate(output.get("evalue"), 240)
        elif "text" in output:
            item["text_preview"] = _truncate(_join_maybe_list(output.get("text")), 240)
        elif isinstance(output.get("data"), dict):
            data = output["data"]
            item["data_keys"] = sorted(str(key) for key in data.keys())
            if "text/plain" in data:
                item["text_preview"] = _truncate(_join_maybe_list(data["text/plain"]), 240)
        summaries.append(item)
    if len(outputs) > max_outputs:
        summaries.append({"truncated_outputs": len(outputs) - max_outputs})
    return summaries


def _join_maybe_list(value: Any) -> str:
    if isinstance(value, list):
        return "".join(str(item) for item in value)
    return str(value or "")


def _outline_cell(index: int, cell: dict[str, Any]) -> dict[str, Any]:
    source = _cell_source(cell)
    outputs = cell.get("outputs") or []
    if not isinstance(outputs, list):
        outputs = []
    cell_type = cell.get("cell_type")
    outline = {
        "index": index,
        "cell_type": cell_type,
        "source_preview": _source_preview(source),
        "source_chars": len(source),
        "output_count": len(outputs),
        "error_count": sum(1 for output in outputs if output.get("output_type") == "error"),
    }
    if cell_type == "markdown":
        outline["headings"] = _markdown_headings(source)
    if cell_type == "code":
        outline["execution_count"] = cell.get("execution_count")
    return outline


def _read_notebook_data(path: str) -> tuple[Path, Path, dict[str, Any]]:
    relative, file_path = _workspace_file(path)
    if file_path.suffix != ".ipynb":
        raise ValueError("Notebook path must end with .ipynb.")
    with file_path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict) or not isinstance(data.get("cells"), list):
        raise ValueError("File is not a valid notebook.")
    return relative, file_path, data


def _write_notebook_data(file_path: Path, data: dict[str, Any]) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def _new_notebook(kernel_name: str) -> dict[str, Any]:
    return {
        "cells": [],
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3" if kernel_name == "python3" else kernel_name,
                "language": "python",
                "name": kernel_name,
            },
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def _new_cell(content: str, cell_type: Literal["code", "markdown", "raw"]) -> dict[str, Any]:
    # nbformat 4.5 (what _new_notebook declares) requires a unique id per cell.
    cell = {"id": uuid.uuid4().hex[:8], "cell_type": cell_type, "metadata": {}, "source": str(content or "")}
    if cell_type == "code":
        cell["execution_count"] = None
        cell["outputs"] = []
    return cell


def _last_cell_source_equals(data: dict[str, Any], content: str, cell_type: str) -> bool:
    cells = data.get("cells") or []
    if not cells:
        return False
    last = cells[-1]
    if last.get("cell_type") != cell_type:
        return False
    return _cell_source(last) == str(content or "")


def _normalized_append_chunk(chunk: str) -> str:
    text = str(chunk or "")
    if not text.endswith("\n"):
        text += "\n"
    return text


def _scratch_file_ends_with(file_path: Path, chunk: str) -> bool:
    if not file_path.is_file():
        return False
    existing = file_path.read_text(encoding="utf-8")
    return existing.endswith(_normalized_append_chunk(chunk))


def _scratch_source_marker(script_rel: Path, script_file: Path) -> dict[str, Any]:
    stat = script_file.stat()
    return {
        "path": script_rel.as_posix(),
        "size_bytes": stat.st_size,
        "mtime": stat.st_mtime,
    }


def _notebook_scratch_marker_matches(data: dict[str, Any], marker: dict[str, Any]) -> bool:
    metadata = data.get("metadata") or {}
    stored = metadata.get("mip_scratch_source")
    if not isinstance(stored, dict):
        return False
    return stored == marker


def _agent_docs_root() -> Path | None:
    configured = os.getenv("MIP_AGENT_DOCS")
    if configured:
        path = Path(configured).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        resolved = path.resolve()
        if resolved.is_dir():
            return resolved
    repo = Path(__file__).resolve().parents[1]
    if (repo / "docs" / "llm").is_dir():
        return repo
    return None


def _wiki_page_key(page: str | None) -> str:
    key = str(page or "00-agent-workspace").strip().replace("\\", "/")
    if key.endswith(".md"):
        key = key[:-3]
    if key not in ALLOWED_WIKI_PAGES:
        allowed = ", ".join(sorted(ALLOWED_WIKI_PAGES))
        raise ValueError(f"Unknown agent wiki page {page!r}; allowed pages: {allowed}")
    return key


def _agent_wiki_path(page: str | None = None) -> tuple[str, Path | None]:
    page_key = _wiki_page_key(page)
    relative_path = ALLOWED_WIKI_PAGES[page_key]
    candidates: list[Path] = []
    agent_root = _agent_docs_root()
    if agent_root is not None:
        candidates.append(agent_root / relative_path)
        candidates.append(agent_root / "docs" / relative_path)
    for path in candidates:
        if path.is_file():
            return page_key, path
    return page_key, None


def _doc_files() -> list[Path]:
    docs_root = _workspace_root() / "docs"
    if not docs_root.is_dir():
        return []
    files = []
    for path in sorted(docs_root.rglob("*.md")):
        if any(part in BLOCKED_PATH_PARTS for part in path.parts):
            continue
        try:
            path.relative_to(docs_root)
        except ValueError:
            continue
        files.append(path)
    return files


def _workspace_display_path(path: Path) -> str:
    return path.relative_to(_workspace_root()).as_posix()


def _markdown_title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def _snippet_for_query(text: str, query: str) -> str:
    lower_text = text.lower()
    terms = [term for term in re.split(r"\W+", query.lower()) if term]
    positions = [lower_text.find(term) for term in terms if lower_text.find(term) >= 0]
    start = max(0, min(positions) - 120) if positions else 0
    snippet = text[start : start + MAX_DOC_SNIPPET_CHARS].strip()
    return _truncate(snippet.replace("\r\n", "\n"), MAX_DOC_SNIPPET_CHARS)


def _section_matches(text: str, topic: str | None) -> list[str]:
    terms = [term for term in re.split(r"\W+", (topic or "").lower()) if term]
    if not terms:
        return [text]
    sections: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        if line.startswith("#") and current:
            section = "\n".join(current).strip()
            lower = section.lower()
            if any(term in lower for term in terms):
                sections.append(section)
            current = [line]
        else:
            current.append(line)
    if current:
        section = "\n".join(current).strip()
        lower = section.lower()
        if any(term in lower for term in terms):
            sections.append(section)
    return sections


async def agent_read_guide(
    page: str | None = None,
    topic: str | None = None,
    max_chars: int = DEFAULT_WIKI_MAX_CHARS,
) -> dict[str, Any]:
    """Read an allowlisted agent wiki page, optionally narrowed by topic."""

    page_key, guide_path = _agent_wiki_path(page)
    relative_path = ALLOWED_WIKI_PAGES[page_key]
    max_chars = _limit(max_chars, DEFAULT_WIKI_MAX_CHARS, MAX_WIKI_CONTENT_CHARS)
    if guide_path is None:
        return {
            "ok": False,
            "page": page_key,
            "path": relative_path.as_posix(),
            "error": "Agent wiki page is missing.",
        }
    text = guide_path.read_text(encoding="utf-8")
    # A missed topic falls back to the whole page and reports matched=false.
    sections = _section_matches(text, topic)
    content = "\n\n".join(sections) if sections else text
    return {
        "ok": True,
        "page": page_key,
        "path": relative_path.as_posix(),
        "topic": topic,
        "matched": bool(sections),
        "content": _truncate(content, max_chars),
        "truncated": len(content) > max_chars,
    }


async def agent_search_docs(query: str, limit: int = 5) -> dict[str, Any]:
    """Search workspace docs and return bounded snippets."""

    query = str(query or "").strip()
    if not query:
        raise ValueError("query is required.")
    limit = _limit(limit, 5, MAX_DOC_RESULTS)
    terms = [term for term in re.split(r"\W+", query.lower()) if term]
    results: list[dict[str, Any]] = []
    for path in _doc_files():
        text = path.read_text(encoding="utf-8")
        haystack = text.lower()
        score = sum(haystack.count(term) for term in terms)
        if score <= 0:
            continue
        results.append(
            {
                "path": _workspace_display_path(path),
                "title": _markdown_title(text, path.name),
                "score": score,
                "snippet": _snippet_for_query(text, query),
            }
        )
    results.sort(key=lambda item: (-int(item["score"]), str(item["path"])))
    return {"ok": True, "query": query, "count": len(results), "results": results[:limit]}


async def notebook_outline(
    path: str,
    max_cells: int = MAX_NOTEBOOK_OUTLINE_CELLS,
) -> dict[str, Any]:
    """Return a bounded notebook outline without full outputs."""

    relative, _file_path, data = _read_notebook_data(path)
    cells = data.get("cells") or []
    max_cells = _limit(max_cells, MAX_NOTEBOOK_OUTLINE_CELLS, MAX_NOTEBOOK_OUTLINE_CELLS)
    visible_cells = cells[:max_cells]
    return {
        "ok": True,
        "path": relative.as_posix(),
        "cell_count": len(cells),
        "cells": [_outline_cell(index, cell) for index, cell in enumerate(visible_cells)],
        "cells_truncated": len(cells) > max_cells,
        "truncated_cell_count": max(0, len(cells) - max_cells),
    }


async def notebook_read_cell(path: str, index: int, max_chars: int = 4000) -> dict[str, Any]:
    """Read one notebook cell source with bounded output summaries."""

    max_chars = _limit(max_chars, 4000, MAX_CELL_READ_CHARS)
    relative, _file_path, data = _read_notebook_data(path)
    cells = data.get("cells") or []
    if index < 0 or index >= len(cells):
        raise IndexError(f"Cell index {index} is out of range for {len(cells)} cells.")
    cell = cells[index]
    source = _cell_source(cell)
    outputs = cell.get("outputs") or []
    if not isinstance(outputs, list):
        outputs = []
    return {
        "ok": True,
        "path": relative.as_posix(),
        "index": index,
        "cell_type": cell.get("cell_type"),
        "source": source[:max_chars],
        "source_chars": len(source),
        "source_truncated": len(source) > max_chars,
        "output_count": len(outputs),
        "error_count": sum(1 for output in outputs if output.get("output_type") == "error"),
        "outputs": _output_summary(outputs),
    }


async def create_notebook(path: str, kernel_name: str = "python3") -> dict[str, Any]:
    """Create an empty notebook under the workspace."""

    relative, file_path = _workspace_file(path)
    if file_path.suffix != ".ipynb":
        raise ValueError("Notebook path must end with .ipynb.")
    if file_path.exists():
        raise FileExistsError(f"Notebook already exists: {relative.as_posix()}")
    data = _new_notebook(kernel_name)
    _write_notebook_data(file_path, data)
    return {"ok": True, "path": relative.as_posix(), "jupyter_path": _server_path(relative)}


async def append_markdown_cell(path: str, content: str) -> dict[str, Any]:
    """Append a markdown cell to a notebook."""

    _validate_cell_content(content, label="markdown")
    relative, file_path, data = _read_notebook_data(path)
    if _last_cell_source_equals(data, content, "markdown"):
        return {
            "ok": True,
            "path": relative.as_posix(),
            "index": len(data["cells"]) - 1,
            "deduplicated": True,
        }
    data["cells"].append(_new_cell(content, "markdown"))
    _write_notebook_data(file_path, data)
    return {"ok": True, "path": relative.as_posix(), "index": len(data["cells"]) - 1}


async def append_code_cell(path: str, content: str) -> dict[str, Any]:
    """Append a code cell to a notebook."""

    _validate_cell_content(content, label="code")
    relative, file_path, data = _read_notebook_data(path)
    if _last_cell_source_equals(data, content, "code"):
        return {
            "ok": True,
            "path": relative.as_posix(),
            "index": len(data["cells"]) - 1,
            "deduplicated": True,
        }
    data["cells"].append(_new_cell(content, "code"))
    _write_notebook_data(file_path, data)
    return {"ok": True, "path": relative.as_posix(), "index": len(data["cells"]) - 1}


async def edit_cell_by_index(
    path: str,
    index: int,
    content: str,
    cell_type: Literal["code", "markdown", "raw"] = "code",
) -> dict[str, Any]:
    """Replace a notebook cell by numeric index."""

    _validate_cell_content(content, label="cell")
    relative, file_path, data = _read_notebook_data(path)
    cells = data.get("cells") or []
    if index < 0 or index >= len(cells):
        raise IndexError(f"Cell index {index} is out of range for {len(cells)} cells.")
    data["cells"][index] = _new_cell(content, cell_type)
    _write_notebook_data(file_path, data)
    return {"ok": True, "path": relative.as_posix(), "index": index, "cell_type": cell_type}


def _execute_notebook(path: Path, data: dict[str, Any], *, timeout: float, index: int | None) -> dict[str, Any]:
    try:
        import nbformat
        from nbclient import NotebookClient
    except ImportError as exc:
        raise RuntimeError("Notebook execution requires nbformat and nbclient.") from exc

    notebook_node = nbformat.from_dict(deepcopy(data))
    cells = notebook_node.cells
    if index is not None:
        if index < 0 or index >= len(cells):
            raise IndexError(f"Cell index {index} is out of range for {len(cells)} cells.")
        selected = deepcopy(notebook_node)
        selected.cells = [deepcopy(cells[cell_index]) for cell_index in range(index + 1)]
        NotebookClient(selected, timeout=timeout, allow_errors=True).execute()
        notebook_node.cells[index] = selected.cells[index]
        executed_indexes = [index]
    else:
        NotebookClient(notebook_node, timeout=timeout, allow_errors=True).execute()
        executed_indexes = list(range(len(cells)))

    nbformat.write(notebook_node, path)
    executed_cell_count = len(executed_indexes)
    executed_cells = [
        _outline_cell(cell_index, json.loads(json.dumps(notebook_node.cells[cell_index])))
        for cell_index in executed_indexes[:MAX_EXECUTED_CELL_SUMMARIES]
    ]
    total_errors = sum(
        1
        for cell_index in executed_indexes
        for output in (notebook_node.cells[cell_index].get("outputs") or [])
        if output.get("output_type") == "error"
    )
    return {
        "ok": total_errors == 0,
        "executed_cells": executed_cells,
        "executed_cell_count": executed_cell_count,
        "executed_cells_truncated": executed_cell_count > MAX_EXECUTED_CELL_SUMMARIES,
        "error_count": total_errors,
    }


async def run_cell_by_index(path: str, index: int, timeout: float = 30.0) -> dict[str, Any]:
    """Execute one notebook cell and its prerequisite code cells in one kernel."""

    relative, file_path, data = _read_notebook_data(path)
    result = _execute_notebook(file_path, data, timeout=float(timeout), index=index)
    result["path"] = relative.as_posix()
    return result


async def run_all_cells(path: str, timeout: float = 30.0) -> dict[str, Any]:
    """Execute all cells in a notebook and write bounded execution summaries."""

    relative, file_path, data = _read_notebook_data(path)
    result = _execute_notebook(file_path, data, timeout=float(timeout), index=None)
    result["path"] = relative.as_posix()
    return result


async def open_file(path: str) -> dict[str, Any]:
    """Open a workspace file in the JupyterLab main area."""

    relative = _workspace_relative_path(path)
    try:
        from jupyter_ai_tools.toolkits import jupyterlab
    except ImportError as exc:
        raise RuntimeError("open_file requires Jupyter AI tools in a running JupyterLab server.") from exc
    return await jupyterlab.open_file(file_path=_server_path(relative))


async def mip_env_status() -> dict[str, Any]:
    """Report whether the MIP platform connection is configured (no secrets or env names)."""

    backend_configured = any(os.getenv(name) for name in ("PLATFORM_BACKEND_URL", "MIP_BASE_URL"))

    token_configured = any(os.getenv(name) for name in ("PLATFORM_TOKEN", "MIP_TOKEN"))
    # Under the notebook operator the hub hands the token out on first use.
    token_configured = token_configured or bool(
        os.getenv("JUPYTERHUB_API_URL") and os.getenv("JUPYTERHUB_API_TOKEN")
    )
    if not token_configured:
        token_configured = any(
            token_file.is_file() and token_file.stat().st_size > 0
            for token_file in (_workspace_root() / "mip_token", _workspace_root() / ".mip_token")
        )

    return {
        "ok": True,
        "connection_configured": backend_configured,
        "authenticated": token_configured,
        "ready": backend_configured and token_configured,
    }


def _mip_client():
    from mip import Client

    return Client.from_env()


def _tool_error(exc: Exception) -> dict[str, Any]:
    return {
        "ok": False,
        "error_type": type(exc).__name__,
        "error": _truncate(str(exc), MAX_METADATA_STRING_CHARS),
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
        return {"value": _truncate(item, MAX_METADATA_ITEM_CHARS)}

    compact: dict[str, Any] = {}
    for key in _METADATA_PRIORITY:
        if key not in item:
            continue
        value = item[key]
        if isinstance(value, str):
            compact[key] = _truncate(value, MAX_METADATA_STRING_CHARS)
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


def _bounded_metadata_response(
    payload: dict[str, Any],
    *,
    list_keys: tuple[str, ...],
) -> dict[str, Any]:
    payload["response_truncated"] = False
    while len(json.dumps(payload, ensure_ascii=False)) > MAX_RESPONSE_JSON_CHARS:
        candidates = [key for key in list_keys if payload.get(key)]
        if not candidates:
            break
        key = max(candidates, key=lambda candidate: len(payload[candidate]))
        payload[key].pop()
        payload["response_truncated"] = True
    return payload


async def mip_catalog_summary(limit: int = DEFAULT_CATALOG_LIMIT) -> dict[str, Any]:
    """Return compact authorized data-model summaries from the MIP platform."""

    limit = _limit(limit, DEFAULT_CATALOG_LIMIT, MAX_LIST_ITEMS)
    try:
        summaries = _mip_client().catalog().summaries()
    except Exception as exc:  # noqa: BLE001 - MCP tools should return structured errors.
        return _tool_error(exc)
    return _bounded_metadata_response(
        {
        "ok": True,
        "count": len(summaries),
        "items": _compact_metadata_items(summaries, limit),
        "truncated": len(summaries) > limit,
        },
        list_keys=("items",),
    )


async def mip_data_model_summary(
    code: str,
    version: str | None = None,
    include_variables: bool = False,
    include_groups: bool = False,
    limit: int = DEFAULT_DATA_MODEL_LIST_LIMIT,
) -> dict[str, Any]:
    """Return compact metadata for one data model."""

    limit = _limit(limit, DEFAULT_DATA_MODEL_LIST_LIMIT, MAX_LIST_ITEMS)
    try:
        data_model = _mip_client().catalog().data_model(code, version=version)
        variables = data_model.list_variables() if include_variables else []
        groups = data_model.list_groups() if include_groups else []
        datasets = data_model.list_datasets()
    except Exception as exc:  # noqa: BLE001 - MCP tools should return structured errors.
        return _tool_error(exc)

    result = {
        "ok": True,
        "summary": _compact_metadata_item(data_model.summary()),
        "datasets": _compact_metadata_items(datasets, limit),
        "datasets_truncated": len(datasets) > limit,
        "groups": _compact_metadata_items(groups, limit),
        "groups_truncated": len(groups) > limit,
        "variables": _compact_metadata_items(variables, limit),
        "variables_truncated": len(variables) > limit,
    }
    return _bounded_metadata_response(
        result,
        list_keys=("datasets", "groups", "variables"),
    )


async def mip_search_variables(
    code: str,
    query: str,
    version: str | None = None,
    limit: int = DEFAULT_VARIABLE_SEARCH_LIMIT,
) -> dict[str, Any]:
    """Search variables in one data model by code or label."""

    limit = _limit(limit, DEFAULT_VARIABLE_SEARCH_LIMIT, MAX_LIST_ITEMS)
    try:
        data_model = _mip_client().catalog().data_model(code, version=version)
        matches = [variable.summary() for variable in data_model.variables.search(query)]
    except Exception as exc:  # noqa: BLE001 - MCP tools should return structured errors.
        return _tool_error(exc)
    return _bounded_metadata_response(
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


async def mip_algorithm_summary(limit: int = DEFAULT_ALGORITHM_SUMMARY_LIMIT) -> dict[str, Any]:
    """Return compact algorithm summaries from the MIP platform."""

    limit = _limit(limit, DEFAULT_ALGORITHM_SUMMARY_LIMIT, MAX_LIST_ITEMS)
    try:
        algorithms = _mip_client().algorithms().list()
        summaries = [algorithm.summary() for algorithm in algorithms]
    except Exception as exc:  # noqa: BLE001 - MCP tools should return structured errors.
        return _tool_error(exc)

    counts_by_type: dict[str, int] = {}
    for item in summaries:
        kind = str(item.get("type") or "unknown")
        counts_by_type[kind] = counts_by_type.get(kind, 0) + 1
    return _bounded_metadata_response(
        {
            "ok": True,
            "count": len(summaries),
            "counts_by_type": counts_by_type,
            "items": _compact_metadata_items(summaries, limit),
            "truncated": len(summaries) > limit,
        },
        list_keys=("items",),
    )


def _scratch_file(path: str) -> tuple[Path, Path]:
    relative = _workspace_relative_path(path)
    if not relative.as_posix().startswith("scratch/"):
        raise ValueError("Scratch paths must stay under scratch/.")
    if not str(relative).endswith(".py"):
        raise ValueError("Scratch file must be a .py script.")
    file_path = _workspace_root() / relative
    return relative, file_path


def _scratch_copy_source(path: str) -> tuple[Path, Path]:
    relative = _workspace_relative_path(path)
    key = relative.as_posix()
    if not str(relative).endswith(".py"):
        raise ValueError("Copy source must be a .py script.")
    if not (key.startswith("examples/") or key.startswith("scratch/")):
        raise ValueError("Copy source must stay under examples/ or scratch/.")
    file_path = _workspace_root() / relative
    return relative, file_path


async def scratch_copy_template(
    dest: str,
    source: str = SCRATCH_TEMPLATE_DEFAULT,
) -> dict[str, Any]:
    """Copy an examples/ or scratch/ script into a new scratch analysis script."""

    src_rel, src_path = _scratch_copy_source(source)
    dest_rel, dest_path = _scratch_file(dest)
    if dest_path.exists():
        raise FileExistsError(f"Destination already exists: {dest_rel.as_posix()}")
    if not src_path.is_file():
        raise FileNotFoundError(f"Template not found: {src_rel.as_posix()}")
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.write_text(src_path.read_text(encoding="utf-8"), encoding="utf-8")
    return {"ok": True, "source": src_rel.as_posix(), "dest": dest_rel.as_posix()}


async def scratch_read(path: str, max_chars: int = 4000) -> dict[str, Any]:
    """Read a bounded scratch .md or .py artifact."""

    relative, file_path = _scratch_read_path(path)
    max_chars = _limit(max_chars, 4000, MAX_SCRATCH_READ_CHARS)
    if not file_path.is_file():
        raise FileNotFoundError(f"Scratch file not found: {relative.as_posix()}")
    text = file_path.read_text(encoding="utf-8")
    return {
        "ok": True,
        "path": relative.as_posix(),
        "content": text[:max_chars],
        "content_chars": len(text),
        "truncated": len(text) > max_chars,
    }


async def scratch_append_lines(path: str, lines: str) -> dict[str, Any]:
    """Append a small chunk of lines to a scratch Python script."""

    relative, file_path = _scratch_file(path)
    chunk = _normalized_append_chunk(lines)
    line_count = len(chunk.splitlines())
    if len(chunk) > MAX_SCRATCH_PAYLOAD_CHARS:
        raise ValueError(
            f"Append exceeds {MAX_SCRATCH_PAYLOAD_CHARS} characters; split into smaller calls."
        )
    if _scratch_file_ends_with(file_path, lines):
        return {
            "ok": True,
            "path": relative.as_posix(),
            "appended_lines": line_count,
            "appended_chars": len(chunk),
            "deduplicated": True,
        }
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("a", encoding="utf-8") as handle:
        handle.write(chunk)
    return {
        "ok": True,
        "path": relative.as_posix(),
        "appended_lines": line_count,
        "appended_chars": len(chunk),
    }


async def scratch_replace_snippet(
    path: str,
    old: str,
    new: str,
) -> dict[str, Any]:
    """Replace one small snippet in a scratch Python script."""

    relative, file_path = _scratch_file(path)
    if len(old) > MAX_SCRATCH_SNIPPET_CHARS or len(new) > MAX_SCRATCH_SNIPPET_CHARS:
        raise ValueError(
            f"Snippet exceeds {MAX_SCRATCH_SNIPPET_CHARS} characters; use smaller replacements."
        )
    if not file_path.is_file():
        raise FileNotFoundError(f"Scratch file not found: {relative.as_posix()}")
    text = file_path.read_text(encoding="utf-8")
    if old not in text:
        raise ValueError("old snippet not found in scratch file.")
    if text.count(old) > 1:
        raise ValueError("old snippet is ambiguous; provide more context.")
    file_path.write_text(text.replace(old, new, 1), encoding="utf-8")
    return {"ok": True, "path": relative.as_posix(), "replaced": True}


async def scratch_write_file(path: str, content: str) -> dict[str, Any]:
    """Write (or overwrite) a complete scratch .py or .md file in one call."""

    relative, file_path = _scratch_read_path(path)
    if not content.strip():
        raise ValueError(
            "Scratch write content is empty; refusing to truncate an existing scratch file."
        )
    if len(content) > MAX_SCRATCH_PAYLOAD_CHARS:
        raise ValueError(
            f"Scratch write exceeds {MAX_SCRATCH_PAYLOAD_CHARS} characters; "
            "split into smaller writes or use scratch-append-lines."
        )
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")
    return {
        "ok": True,
        "path": relative.as_posix(),
        "written_chars": len(content),
    }


def _has_cell_markers(source: str) -> bool:
    return any(line.strip().startswith("# %%") for line in source.splitlines())


def _split_script_into_cells(source: str) -> list[tuple[str, str]]:
    """Split a .py script into (cell_type, content) pairs.

    With ``# %%`` / ``# %% [markdown]`` markers, split into multiple cells.
    Without markers, treat the whole file as one code cell.
    """
    if not source.strip():
        return []
    if not _has_cell_markers(source):
        return [("code", source.strip())]

    cells: list[tuple[str, str]] = []
    current_type = "code"
    current_lines: list[str] = []
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith("# %%") and "[markdown]" in stripped.lower():
            if current_lines:
                cells.append((current_type, "\n".join(current_lines).strip()))
                current_lines = []
            current_type = "markdown"
            continue
        if stripped == "# %%" or (stripped.startswith("# %%") and "markdown" not in stripped.lower()):
            if current_lines:
                cells.append((current_type, "\n".join(current_lines).strip()))
                current_lines = []
            current_type = "code"
            continue
        if current_type == "markdown" and stripped.startswith("#"):
            current_lines.append(line.lstrip("# ").lstrip())
        else:
            current_lines.append(line)
    if current_lines:
        cells.append((current_type, "\n".join(current_lines).strip()))
    return [cell for cell in cells if cell[1]]


_SCRATCH_TO_NOTEBOOK_HINT = "Next: open-file and notebook-outline on the notebook path."


async def scratch_to_notebook(
    script_path: str,
    notebook_path: str,
    *,
    title: str | None = None,
) -> dict[str, Any]:
    """Transfer a verified scratch/*.py script into a notebook incrementally."""

    script_rel, script_file = _scratch_file(script_path)
    nb_rel, nb_file = _workspace_file(notebook_path)
    if nb_file.suffix != ".ipynb":
        raise ValueError("Notebook path must end with .ipynb.")
    if not script_file.is_file():
        raise FileNotFoundError(f"Script not found: {script_rel.as_posix()}")
    source = script_file.read_text(encoding="utf-8")
    cells = _split_script_into_cells(source)
    if not cells:
        raise ValueError(
            "Script is empty; write code first, or add # %% section markers to split cells."
        )

    source_marker = _scratch_source_marker(script_rel, script_file)

    if nb_file.exists():
        _, _, data = _read_notebook_data(notebook_path)
        if _notebook_scratch_marker_matches(data, source_marker):
            return {
                "ok": True,
                "script": script_rel.as_posix(),
                "notebook": nb_rel.as_posix(),
                "cell_count": len(data["cells"]),
                "deduplicated": True,
                "hint": _SCRATCH_TO_NOTEBOOK_HINT,
            }
    else:
        data = _new_notebook("python3")

    if title:
        data["cells"].append(_new_cell(f"# {title}\n\nTransferred from `{script_rel.as_posix()}`.", "markdown"))

    for cell_type, content in cells:
        if len(content) > MAX_CELL_READ_CHARS:
            raise ValueError(
                f"Transferred {cell_type} cell exceeds {MAX_CELL_READ_CHARS} characters; "
                "split the script into smaller # %% sections."
            )
        data["cells"].append(_new_cell(content, cell_type if cell_type in {"code", "markdown"} else "code"))

    metadata = data.setdefault("metadata", {})
    metadata["mip_scratch_source"] = source_marker

    _write_notebook_data(nb_file, data)
    return {
        "ok": True,
        "script": script_rel.as_posix(),
        "notebook": nb_rel.as_posix(),
        "cell_count": len(data["cells"]),
        "hint": _SCRATCH_TO_NOTEBOOK_HINT,
    }


def _scratch_read_path(path: str) -> tuple[Path, Path]:
    relative = _workspace_relative_path(path)
    if not relative.as_posix().startswith("scratch/"):
        raise ValueError("Scratch read paths must stay under scratch/.")
    if relative.suffix not in {".md", ".py"}:
        raise ValueError("Scratch read supports .md and .py files only.")
    file_path = _workspace_root() / relative
    return relative, file_path


def _first_line_summary(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith('"""') or stripped.startswith("'''"):
            return stripped.strip("\"'")
        if stripped.startswith("#"):
            return stripped.lstrip("# ").strip()
        return stripped[:MAX_METADATA_STRING_CHARS]
    return ""


async def scratch_list() -> dict[str, Any]:
    """List scratch/*.py and scratch/*.md artifacts for resume."""

    scratch_dir = _workspace_root() / "scratch"
    items: list[dict[str, Any]] = []
    if scratch_dir.is_dir():
        for path in sorted(scratch_dir.iterdir()):
            if path.name.startswith("."):
                continue
            if path.suffix not in {".py", ".md"}:
                continue
            stat = path.stat()
            items.append(
                {
                    "path": f"scratch/{path.name}",
                    "size_bytes": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                    "first_line": _first_line_summary(path),
                }
            )
    truncated = len(items) > MAX_SCRATCH_LIST_ITEMS
    return _bounded_metadata_response(
        {
            "ok": True,
            "count": len(items),
            "items": items[:MAX_SCRATCH_LIST_ITEMS],
            "truncated": truncated,
        },
        list_keys=("items",),
    )
