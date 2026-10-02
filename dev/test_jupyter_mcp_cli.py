"""Tests for jupyter_mcp_cli shell bridge."""

from __future__ import annotations

import json
import os

import pytest
from unittest.mock import patch

from dev import jupyter_mcp_cli


def test_read_guide_stroke_recipe_page_routes_to_agent_read_guide() -> None:
    args = jupyter_mcp_cli._parser().parse_args(
        ["read-guide", "--page", "recipes/stroke-analysis", "--topic", "pipeline"]
    )
    name, arguments = jupyter_mcp_cli._tool_call_for_args(args)
    assert name == "agent_read_guide"
    assert arguments["page"] == "recipes/stroke-analysis"
    assert arguments["topic"] == "pipeline"


def test_legacy_read_wiki_subcommand_removed() -> None:
    with pytest.raises(SystemExit):
        jupyter_mcp_cli._parser().parse_args(["read-wiki"])


def test_mip_data_model_summary_requires_version_flag() -> None:
    args = jupyter_mcp_cli._parser().parse_args(
        ["mip-data-model-summary", "stroke", "--version", "3.7"]
    )
    name, arguments = jupyter_mcp_cli._tool_call_for_args(args)
    assert name == "mip_data_model_summary"
    assert arguments == {
        "code": "stroke",
        "version": "3.7",
        "include_variables": False,
        "include_groups": False,
        "limit": jupyter_mcp_cli.tools.DEFAULT_DATA_MODEL_LIST_LIMIT,
    }


def test_parse_sse_response_reads_data_lines() -> None:
    body = b"event: message\ndata: {\"ok\": true}\n\n"
    parsed = jupyter_mcp_cli._parse_sse_response(body)
    assert parsed == {"ok": True}


def test_algorithm_examples_exists_with_cell_markers() -> None:
    from pathlib import Path

    repo = Path(__file__).resolve().parents[1]
    examples = repo / "workspace" / "examples" / "algorithm_examples.py"
    assert examples.is_file()
    text = examples.read_text(encoding="utf-8")
    assert "# %%" in text
    assert "Pipeline" in text


def test_scratch_copy_template_cli_routes() -> None:
    args = jupyter_mcp_cli._parser().parse_args(
        ["scratch-copy-template", "scratch/my_analysis.py"]
    )
    name, arguments = jupyter_mcp_cli._tool_call_for_args(args)
    assert name == "scratch_copy_template"
    assert arguments["dest"] == "scratch/my_analysis.py"


def test_scratch_to_notebook_cli_routes() -> None:
    args = jupyter_mcp_cli._parser().parse_args(
        [
            "scratch-to-notebook",
            "scratch/my_analysis.py",
            "scratch/my_analysis.ipynb",
            "--title",
            "My analysis",
        ]
    )
    name, arguments = jupyter_mcp_cli._tool_call_for_args(args)
    assert name == "scratch_to_notebook"
    assert arguments["title"] == "My analysis"


def test_scratch_list_cli_routes() -> None:
    args = jupyter_mcp_cli._parser().parse_args(["scratch-list"])
    name, arguments = jupyter_mcp_cli._tool_call_for_args(args)
    assert name == "scratch_list"
    assert arguments == {}


def test_read_guide_index_page_routes_to_agent_read_guide() -> None:
    args = jupyter_mcp_cli._parser().parse_args(["read-guide", "--page", "index"])
    name, arguments = jupyter_mcp_cli._tool_call_for_args(args)
    assert name == "agent_read_guide"
    assert arguments["page"] == "index"


def test_scratch_read_cli_routes() -> None:
    args = jupyter_mcp_cli._parser().parse_args(
        ["scratch-read", "scratch/notes.md", "--max-chars", "2000"]
    )
    name, arguments = jupyter_mcp_cli._tool_call_for_args(args)
    assert name == "scratch_read"
    assert arguments == {"path": "scratch/notes.md", "max_chars": 2000}


def test_scratch_write_file_cli_routes() -> None:
    args = jupyter_mcp_cli._parser().parse_args(
        ["scratch-write-file", "scratch/foo.py", "print(1)", "print(2)"]
    )
    name, arguments = jupyter_mcp_cli._tool_call_for_args(args)
    assert name == "scratch_write_file"
    # One inline argument is one line, so the script keeps its line structure.
    assert arguments == {"path": "scratch/foo.py", "content": "print(1)\nprint(2)"}
    args = jupyter_mcp_cli._parser().parse_args(
        ["scratch-write-file", "scratch/foo.py", "--content-file", "snippet.txt"]
    )
    assert args.content_file == "snippet.txt"


def test_content_file_rejects_outside_workspace(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    args = jupyter_mcp_cli._parser().parse_args(
        ["append-code", "scratch/foo.ipynb", "--content-file", str(outside)]
    )
    with patch.dict(os.environ, {"MIP_JUPYTER_ROOT": str(workspace)}):
        with pytest.raises(ValueError, match="Path must stay under the Jupyter workspace"):
            jupyter_mcp_cli._content_from_args(args)


def test_content_file_reads_workspace_relative_path(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    snippet = workspace / "snippet.txt"
    snippet.write_text("print('ok')", encoding="utf-8")
    args = jupyter_mcp_cli._parser().parse_args(
        ["append-code", "scratch/foo.ipynb", "--content-file", "snippet.txt"]
    )
    with patch.dict(os.environ, {"MIP_JUPYTER_ROOT": str(workspace)}):
        content = jupyter_mcp_cli._content_from_args(args)
    assert content == "print('ok')"


def test_parse_sse_response_falls_back_to_json_body() -> None:
    payload = {"result": {"content": []}}
    parsed = jupyter_mcp_cli._parse_sse_response(json.dumps(payload).encode("utf-8"))
    assert parsed == payload
