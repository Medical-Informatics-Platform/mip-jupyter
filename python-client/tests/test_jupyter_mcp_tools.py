import asyncio
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
CLIENT = ROOT / "python-client"
for path in (ROOT, CLIENT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from mip_jupyter_dev import jupyter_mcp_tools as tools  # noqa: E402


def run(coro):
    return asyncio.run(coro)


class FakeVariable:
    def __init__(self, code, label):
        self.code = code
        self.label = label

    def summary(self):
        return {"code": self.code, "label": self.label, "type": "integer"}


class FakeVariables:
    def search(self, query):
        return [FakeVariable("nihss", f"NIHSS {query}")]


class FakeDataModel:
    variables = FakeVariables()

    def summary(self):
        return {"code": "stroke", "version": "3.7", "n_variables": 1, "n_datasets": 1}

    def list_datasets(self):
        return [{"code": "ds", "label": "Dataset", "n_variables": 1}]

    def list_groups(self):
        return [{"code": "clinical", "label": "Clinical"}]

    def list_variables(self):
        return [{"code": "nihss", "label": "NIHSS", "type": "integer"}]


class FakeCatalog:
    def summaries(self):
        return [
            {"code": "stroke", "version": "3.7", "label": "Stroke"},
            {"code": "dementia", "version": "0.1", "label": "Dementia"},
        ]

    def data_model(self, code, version=None):
        self.last_lookup = (code, version)
        return FakeDataModel()


class FakeAlgorithm:
    def __init__(self, name, kind):
        self.name = name
        self.kind = kind

    def summary(self):
        return {"name": self.name, "label": self.name.title(), "type": self.kind, "desc": None}


class FakeAlgorithms:
    def list(self):
        return [FakeAlgorithm("describe", "statistics"), FakeAlgorithm("logistic_regression", "model")]


class FakeClient:
    def __init__(self):
        self._catalog = FakeCatalog()
        self._algorithms = FakeAlgorithms()

    def catalog(self):
        return self._catalog

    def algorithms(self):
        return self._algorithms


class TestJupyterMcpTools(unittest.TestCase):
    def _workspace(self):
        tmp = tempfile.TemporaryDirectory()
        workspace = Path(tmp.name) / "workspace"
        workspace.mkdir()
        (workspace / "docs").mkdir()
        return tmp, workspace

    def test_agent_docs_search_is_bounded_to_workspace_docs(self):
        tmp, workspace = self._workspace()
        self.addCleanup(tmp.cleanup)
        repo = workspace.parent
        agent_docs = repo / "agent-docs"
        (agent_docs / "llm" / "wiki").mkdir(parents=True)
        (agent_docs / "llm" / "wiki" / "00-agent-workspace.md").write_text(
            "# Agent Workspace Guide\n\n## Scratch\n\nUse scratch notebooks for NIHSS analysis.",
            encoding="utf-8",
        )
        (workspace / "docs" / "quickstart.md").write_text(
            "# Quickstart\n\nNIHSS variables are discovered through metadata summaries.",
            encoding="utf-8",
        )
        (workspace.parent / "outside.md").write_text("NIHSS SECRET_OUTSIDE", encoding="utf-8")

        with patch.dict(
            os.environ,
            {"MIP_JUPYTER_ROOT": str(workspace), "MIP_AGENT_DOCS": str(agent_docs)},
        ):
            guide = run(tools.agent_read_guide(topic="scratch"))
            result = run(tools.agent_search_docs("NIHSS", limit=1))

        serialized = json.dumps(result)
        self.assertTrue(guide["ok"])
        self.assertEqual(len(result["results"]), 1)
        self.assertTrue(result["results"][0]["path"].startswith("docs/"))
        self.assertNotIn("SECRET_OUTSIDE", serialized)
        self.assertLessEqual(len(result["results"][0]["snippet"]), tools.MAX_DOC_SNIPPET_CHARS)

    def test_agent_wiki_page_reads_are_allowlisted_and_bounded(self):
        tmp, workspace = self._workspace()
        self.addCleanup(tmp.cleanup)
        agent_docs = workspace.parent / "agent-docs"
        wiki = agent_docs / "llm" / "wiki"
        wiki.mkdir(parents=True)
        (wiki / "00-agent-workspace.md").write_text("# Workspace\n\nGuide", encoding="utf-8")
        (wiki / "05-env-and-backend.md").write_text(
            "# Env\n\n" + "Client.from_env details " * 500,
            encoding="utf-8",
        )

        with patch.dict(
            os.environ,
            {"MIP_JUPYTER_ROOT": str(workspace), "MIP_AGENT_DOCS": str(agent_docs)},
        ):
            page = run(tools.agent_read_guide(page="05-env-and-backend"))

        self.assertTrue(page["ok"])
        self.assertEqual(page["page"], "05-env-and-backend")
        self.assertLessEqual(len(page["content"]), tools.MAX_WIKI_CONTENT_CHARS)
        self.assertTrue(page["truncated"])

        with self.assertRaises(ValueError):
            run(tools.agent_read_guide(page="../05-env-and-backend"))

    def test_stroke_recipe_wiki_page_is_allowlisted(self):
        tmp, workspace = self._workspace()
        self.addCleanup(tmp.cleanup)
        agent_docs = workspace.parent / "agent-docs"
        wiki = agent_docs / "llm" / "wiki" / "recipes"
        wiki.mkdir(parents=True)
        (wiki / "stroke-analysis.md").write_text(
            "# Stroke\n\nUse pipeline.t_test and logistic_regression.",
            encoding="utf-8",
        )

        with patch.dict(
            os.environ,
            {"MIP_JUPYTER_ROOT": str(workspace), "MIP_AGENT_DOCS": str(agent_docs)},
        ):
            page = run(tools.agent_read_guide(page="recipes/stroke-analysis"))

        self.assertTrue(page["ok"])
        self.assertEqual(page["page"], "recipes/stroke-analysis")
        self.assertIn("pipeline.t_test", page["content"])

    def test_read_guide_topic_match_and_unmatched_fallback(self):
        tmp, workspace = self._workspace()
        self.addCleanup(tmp.cleanup)
        agent_docs = workspace.parent / "agent-docs"
        wiki = agent_docs / "llm" / "wiki"
        wiki.mkdir(parents=True)
        (wiki / "04-jupyter-mcp.md").write_text(
            "# Jupyter MCP\n\n"
            "## Tool payload safety\n\nKeep args small.\n\n"
            "## Common commands\n\nread-guide usage.",
            encoding="utf-8",
        )

        with patch.dict(
            os.environ,
            {"MIP_JUPYTER_ROOT": str(workspace), "MIP_AGENT_DOCS": str(agent_docs)},
        ):
            matched = run(tools.agent_read_guide(page="04-jupyter-mcp", topic="payload"))
            unmatched = run(tools.agent_read_guide(page="04-jupyter-mcp", topic="zzzz_nonexistent"))

        self.assertTrue(matched["ok"])
        self.assertIn("Keep args small", matched["content"])

        # Unmatched topic must fall back to the full page, never empty content.
        self.assertTrue(unmatched["ok"])
        self.assertFalse(unmatched["matched"])
        self.assertIn("Common commands", unmatched["content"])
        self.assertTrue(matched["matched"])

    def test_notebook_outline_excludes_full_outputs_and_cell_read_limits_source(self):
        tmp, workspace = self._workspace()
        self.addCleanup(tmp.cleanup)
        notebook = workspace / "scratch" / "probe.ipynb"
        notebook.parent.mkdir()
        notebook.write_text(
            json.dumps(
                {
                    "cells": [
                        {"cell_type": "markdown", "metadata": {}, "source": "# Intro\n" + "x" * 80},
                        {
                            "cell_type": "code",
                            "execution_count": 1,
                            "metadata": {},
                            "source": "print('ok')",
                            "outputs": [
                                {"output_type": "stream", "name": "stdout", "text": "SECRET_OUTPUT" + "y" * 500}
                            ],
                        },
                    ],
                    "metadata": {},
                    "nbformat": 4,
                    "nbformat_minor": 5,
                }
            ),
            encoding="utf-8",
        )

        with patch.dict(os.environ, {"MIP_JUPYTER_ROOT": str(workspace)}):
            outline = run(tools.notebook_outline("scratch/probe.ipynb"))
            cell = run(tools.notebook_read_cell("scratch/probe.ipynb", 0, max_chars=10))

        self.assertEqual(outline["cell_count"], 2)
        self.assertNotIn("SECRET_OUTPUT", json.dumps(outline))
        self.assertEqual(cell["source"], "# Intro\nxx")
        self.assertTrue(cell["source_truncated"])

    def test_notebook_outline_truncates_large_notebooks(self):
        tmp, workspace = self._workspace()
        self.addCleanup(tmp.cleanup)
        notebook = workspace / "scratch" / "large.ipynb"
        notebook.parent.mkdir()
        notebook.write_text(
            json.dumps(
                {
                    "cells": [
                        {"cell_type": "code", "metadata": {}, "source": f"cell_{index}"}
                        for index in range(105)
                    ],
                    "metadata": {},
                    "nbformat": 4,
                    "nbformat_minor": 5,
                }
            ),
            encoding="utf-8",
        )

        with patch.dict(os.environ, {"MIP_JUPYTER_ROOT": str(workspace)}):
            outline = run(tools.notebook_outline("scratch/large.ipynb", max_cells=10))

        self.assertEqual(outline["cell_count"], 105)
        self.assertEqual(len(outline["cells"]), 10)
        self.assertTrue(outline["cells_truncated"])
        self.assertEqual(outline["truncated_cell_count"], 95)

    def test_create_append_and_edit_notebook_under_workspace(self):
        tmp, workspace = self._workspace()
        self.addCleanup(tmp.cleanup)

        with patch.dict(os.environ, {"MIP_JUPYTER_ROOT": str(workspace)}):
            created = run(tools.create_notebook("scratch/mcp_probe.ipynb"))
            first = run(tools.append_markdown_cell("scratch/mcp_probe.ipynb", "# Probe"))
            second = run(tools.append_code_cell("scratch/mcp_probe.ipynb", "1 + 1"))
            edited = run(tools.edit_cell_by_index("scratch/mcp_probe.ipynb", 0, "# Updated", "markdown"))
            outline = run(tools.notebook_outline("scratch/mcp_probe.ipynb"))

        self.assertTrue(created["ok"])
        self.assertEqual(first["index"], 0)
        self.assertEqual(second["index"], 1)
        self.assertEqual(edited["cell_type"], "markdown")
        self.assertEqual(outline["cells"][0]["headings"], ["Updated"])
        data = json.loads((workspace / "scratch" / "mcp_probe.ipynb").read_text(encoding="utf-8"))
        ids = [cell.get("id") for cell in data["cells"]]
        self.assertTrue(all(ids) and len(set(ids)) == len(ids))

    def test_mip_env_status_does_not_expose_token_values(self):
        tmp, workspace = self._workspace()
        self.addCleanup(tmp.cleanup)
        secret = "TOP_SECRET_TOKEN"

        with patch.dict(
            os.environ,
            {"MIP_JUPYTER_ROOT": str(workspace), "PLATFORM_BACKEND_URL": "http://backend/services", "MIP_TOKEN": secret},
        ):
            status = run(tools.mip_env_status())

        serialized = json.dumps(status)
        self.assertTrue(status["connection_configured"])
        self.assertTrue(status["authenticated"])
        self.assertTrue(status["ready"])
        self.assertNotIn(secret, serialized)

    def test_mip_metadata_tools_use_mocked_client(self):
        fake_client = FakeClient()
        with patch("mip.Client.from_env", return_value=fake_client) as from_env:
            catalog = run(tools.mip_catalog_summary(limit=1))
            model = run(tools.mip_data_model_summary("stroke", version="3.7", include_variables=True))
            variables = run(tools.mip_search_variables("stroke", "NIHSS", version="3.7", limit=5))
            algorithms = run(tools.mip_algorithm_summary())

        self.assertEqual(from_env.call_count, 4)
        self.assertEqual(catalog["items"], [{"code": "stroke", "version": "3.7", "label": "Stroke"}])
        self.assertTrue(catalog["truncated"])
        self.assertEqual(model["summary"]["code"], "stroke")
        self.assertEqual(model["variables"][0]["code"], "nihss")
        self.assertEqual(model["groups"], [])
        self.assertEqual(variables["items"][0]["code"], "nihss")
        self.assertEqual(algorithms["counts_by_type"], {"statistics": 1, "model": 1})

    def test_mip_metadata_responses_compact_large_items(self):
        class LargeCatalog(FakeCatalog):
            def summaries(self):
                return [
                    {
                        "code": f"model-{index}",
                        "label": "x" * 2000,
                        "description": "secretly verbose metadata",
                    }
                    for index in range(100)
                ]

        fake_client = FakeClient()
        fake_client._catalog = LargeCatalog()
        with patch("mip.Client.from_env", return_value=fake_client):
            result = run(tools.mip_catalog_summary(limit=100))

        serialized = json.dumps(result)
        self.assertLessEqual(len(serialized), tools.MAX_RESPONSE_JSON_CHARS)
        self.assertTrue(result["truncated"])
        self.assertLessEqual(len(result["items"]), tools.MAX_LIST_ITEMS)
        self.assertLessEqual(len(result["items"][0]["label"]), tools.MAX_METADATA_STRING_CHARS)

    def test_stroke_recipe_allowlist_includes_coverage_guidance(self):
        tmp, workspace = self._workspace()
        self.addCleanup(tmp.cleanup)
        repo = Path(__file__).resolve().parents[2]
        with patch.dict(os.environ, {"MIP_JUPYTER_ROOT": str(workspace), "MIP_AGENT_DOCS": str(repo)}):
            guide = run(tools.agent_read_guide(page="recipes/stroke-analysis", max_chars=8000))

        self.assertTrue(guide["ok"])
        content = guide["content"]
        self.assertIn("never mix SSR", content)
        self.assertIn("num_dtps", content)
        self.assertIn("inputdata()", content)
        self.assertIn("examples/algorithm_examples.py", content)
        self.assertIn("scratch-to-notebook", content)

    def test_scratch_copy_template_and_to_notebook(self):
        tmp, workspace = self._workspace()
        self.addCleanup(tmp.cleanup)
        repo = Path(__file__).resolve().parents[2]
        examples = repo / "workspace" / "examples" / "algorithm_examples.py"
        example_dir = workspace / "examples"
        example_dir.mkdir(parents=True, exist_ok=True)
        (example_dir / "algorithm_examples.py").write_text(
            examples.read_text(encoding="utf-8"),
            encoding="utf-8",
        )

        with patch.dict(os.environ, {"MIP_JUPYTER_ROOT": str(workspace)}):
            copied = run(
                tools.scratch_copy_template(
                    "scratch/test_analysis.py",
                    source="examples/algorithm_examples.py",
                )
            )
            appended = run(
                tools.scratch_append_lines(
                    "scratch/test_analysis.py",
                    lines="# appended line\n",
                )
            )
            replaced = run(
                tools.scratch_replace_snippet(
                    "scratch/test_analysis.py",
                    old="DATA_MODEL = \"Stroke 3.7\"",
                    new="DATA_MODEL = \"Stroke 3.7\"  # test",
                )
            )
            notebook = run(
                tools.scratch_to_notebook(
                    "scratch/test_analysis.py",
                    "scratch/test_analysis.ipynb",
                    title="Test analysis",
                )
            )

        self.assertTrue(copied["ok"])
        self.assertTrue(appended["ok"])
        self.assertTrue(replaced["ok"])
        self.assertTrue(notebook["ok"])
        self.assertTrue((workspace / "scratch" / "test_analysis.ipynb").exists())

    def test_scratch_append_lines_rejects_oversized_chunk(self):
        tmp, workspace = self._workspace()
        self.addCleanup(tmp.cleanup)
        (workspace / "scratch").mkdir(parents=True, exist_ok=True)
        (workspace / "scratch" / "foo.py").write_text("x = 1\n", encoding="utf-8")

        with patch.dict(os.environ, {"MIP_JUPYTER_ROOT": str(workspace)}):
            with self.assertRaises(ValueError):
                run(
                    tools.scratch_append_lines(
                        "scratch/foo.py",
                        lines="x" * (tools.MAX_SCRATCH_PAYLOAD_CHARS + 1),
                    )
                )

    def test_scratch_write_file_writes_overwrites_and_rejects_bad_path(self):
        tmp, workspace = self._workspace()
        self.addCleanup(tmp.cleanup)
        (workspace / "scratch").mkdir(parents=True, exist_ok=True)

        with patch.dict(os.environ, {"MIP_JUPYTER_ROOT": str(workspace)}):
            written = run(tools.scratch_write_file("scratch/foo.py", "x = 1\n"))
            run(tools.scratch_write_file("scratch/foo.py", "y = 2\n"))
            read_back = run(tools.scratch_read("scratch/foo.py"))
            with self.assertRaises(ValueError):
                run(tools.scratch_write_file("../evil.py", "x"))
            with self.assertRaises(ValueError):
                run(tools.scratch_write_file("scratch/foo.py", "   "))
            with self.assertRaises(ValueError):
                run(
                    tools.scratch_write_file(
                        "scratch/big.py", "z" * (tools.MAX_SCRATCH_PAYLOAD_CHARS + 1)
                    )
                )

        self.assertTrue(written["ok"])
        self.assertEqual(read_back["content"], "y = 2\n")

    def test_scratch_list_returns_py_and_md_artifacts(self):
        tmp, workspace = self._workspace()
        self.addCleanup(tmp.cleanup)
        scratch = workspace / "scratch"
        scratch.mkdir(parents=True, exist_ok=True)
        (scratch / "analysis.py").write_text('"""Audit script."""\n', encoding="utf-8")
        (scratch / "notes.md").write_text("# Notes\n", encoding="utf-8")
        (scratch / "ignored.txt").write_text("skip\n", encoding="utf-8")

        with patch.dict(os.environ, {"MIP_JUPYTER_ROOT": str(workspace)}):
            result = run(tools.scratch_list())

        self.assertTrue(result["ok"])
        paths = {item["path"] for item in result["items"]}
        self.assertIn("scratch/analysis.py", paths)
        self.assertIn("scratch/notes.md", paths)
        self.assertNotIn("scratch/ignored.txt", paths)
        analysis = next(item for item in result["items"] if item["path"] == "scratch/analysis.py")
        self.assertIn("Audit script", analysis["first_line"])

    def test_cell_write_cap_rejects_oversized_content(self):
        with self.assertRaises(ValueError):
            tools._validate_cell_content("x" * (tools.MAX_CELL_WRITE_CHARS + 1))

    def test_scratch_read_md_file(self):
        tmp, workspace = self._workspace()
        self.addCleanup(tmp.cleanup)
        scratch = workspace / "scratch"
        scratch.mkdir(parents=True, exist_ok=True)
        (scratch / "notes.md").write_text("# Notes\nhello\n", encoding="utf-8")

        with patch.dict(os.environ, {"MIP_JUPYTER_ROOT": str(workspace)}):
            read_back = run(tools.scratch_read("scratch/notes.md", max_chars=200))

        self.assertTrue(read_back["ok"])
        self.assertIn("Notes", read_back["content"])

    def test_scratch_append_lines_deduplicates_identical_chunk(self):
        tmp, workspace = self._workspace()
        self.addCleanup(tmp.cleanup)
        (workspace / "scratch").mkdir(parents=True, exist_ok=True)
        (workspace / "scratch" / "foo.py").write_text("x = 1\n", encoding="utf-8")

        with patch.dict(os.environ, {"MIP_JUPYTER_ROOT": str(workspace)}):
            first = run(tools.scratch_append_lines("scratch/foo.py", lines="# added\n"))
            second = run(tools.scratch_append_lines("scratch/foo.py", lines="# added\n"))

        self.assertTrue(first["ok"])
        self.assertNotIn("deduplicated", first)
        self.assertTrue(second.get("deduplicated"))

    def test_scratch_to_notebook_deduplicates_repeat_transfer(self):
        tmp, workspace = self._workspace()
        self.addCleanup(tmp.cleanup)
        repo = Path(__file__).resolve().parents[2]
        examples = repo / "workspace" / "examples" / "algorithm_examples.py"
        example_dir = workspace / "examples"
        example_dir.mkdir(parents=True, exist_ok=True)
        (example_dir / "algorithm_examples.py").write_text(
            examples.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (workspace / "scratch").mkdir(parents=True, exist_ok=True)

        with patch.dict(os.environ, {"MIP_JUPYTER_ROOT": str(workspace)}):
            copied = run(
                tools.scratch_copy_template(
                    "scratch/test_analysis.py",
                    source="examples/algorithm_examples.py",
                )
            )
            first = run(
                tools.scratch_to_notebook(
                    "scratch/test_analysis.py",
                    "scratch/test_analysis.ipynb",
                    title="Test analysis",
                )
            )
            second = run(
                tools.scratch_to_notebook(
                    "scratch/test_analysis.py",
                    "scratch/test_analysis.ipynb",
                    title="Test analysis",
                )
            )

        self.assertTrue(copied["ok"])
        self.assertTrue(first["ok"])
        self.assertTrue(second.get("deduplicated"))
        self.assertEqual(first["cell_count"], second["cell_count"])
        self.assertIn("open-file", first.get("hint", ""))
        self.assertIn("open-file", second.get("hint", ""))

    def test_scratch_to_notebook_unmarked_script_is_one_code_cell(self):
        tmp, workspace = self._workspace()
        self.addCleanup(tmp.cleanup)
        scratch = workspace / "scratch"
        scratch.mkdir(parents=True, exist_ok=True)
        (scratch / "plain.py").write_text(
            "from __future__ import annotations\n\nx = 1\nprint(x)\n",
            encoding="utf-8",
        )

        with patch.dict(os.environ, {"MIP_JUPYTER_ROOT": str(workspace)}):
            result = run(
                tools.scratch_to_notebook(
                    "scratch/plain.py",
                    "scratch/plain.ipynb",
                    title="Plain script",
                )
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["script"], "scratch/plain.py")
        self.assertEqual(result["notebook"], "scratch/plain.ipynb")
        self.assertEqual(result["cell_count"], 2)  # title markdown + one code cell
        self.assertIn("notebook-outline", result["hint"])
        nb = json.loads((scratch / "plain.ipynb").read_text(encoding="utf-8"))
        self.assertEqual(nb["cells"][0]["cell_type"], "markdown")
        self.assertEqual(nb["cells"][1]["cell_type"], "code")
        self.assertIn("x = 1", "".join(nb["cells"][1]["source"]))

    def test_scratch_to_notebook_splits_on_cell_markers(self):
        tmp, workspace = self._workspace()
        self.addCleanup(tmp.cleanup)
        scratch = workspace / "scratch"
        scratch.mkdir(parents=True, exist_ok=True)
        (scratch / "marked.py").write_text(
            "# %% [markdown]\n# # Intro\n\n# %%\na = 1\n\n# %%\nb = 2\n",
            encoding="utf-8",
        )

        with patch.dict(os.environ, {"MIP_JUPYTER_ROOT": str(workspace)}):
            result = run(
                tools.scratch_to_notebook(
                    "scratch/marked.py",
                    "scratch/marked.ipynb",
                )
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["cell_count"], 3)
        self.assertIn("open-file", result["hint"])
        nb = json.loads((scratch / "marked.ipynb").read_text(encoding="utf-8"))
        types = [cell["cell_type"] for cell in nb["cells"]]
        self.assertEqual(types, ["markdown", "code", "code"])
        self.assertIn("Intro", "".join(nb["cells"][0]["source"]))
        self.assertIn("a = 1", "".join(nb["cells"][1]["source"]))
        self.assertIn("b = 2", "".join(nb["cells"][2]["source"]))

    def test_run_cell_executes_prerequisite_code_cells(self):
        try:
            import nbclient  # noqa: F401
        except ImportError:
            self.skipTest("nbclient is required for notebook execution tests")

        tmp, workspace = self._workspace()
        self.addCleanup(tmp.cleanup)
        notebook = workspace / "scratch" / "prefix.ipynb"
        notebook.parent.mkdir(parents=True, exist_ok=True)
        notebook.write_text(
            json.dumps(
                {
                    "cells": [
                        {
                            "id": "prefix",
                            "cell_type": "code",
                            "execution_count": None,
                            "metadata": {},
                            "source": "prefix_value = 42",
                            "outputs": [],
                        },
                        {
                            "id": "print",
                            "cell_type": "code",
                            "execution_count": None,
                            "metadata": {},
                            "source": "print(prefix_value)",
                            "outputs": [],
                        },
                    ],
                    "metadata": {
                        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                        "language_info": {"name": "python"},
                    },
                    "nbformat": 4,
                    "nbformat_minor": 5,
                }
            ),
            encoding="utf-8",
        )

        with patch.dict(os.environ, {"MIP_JUPYTER_ROOT": str(workspace)}):
            result = run(tools.run_cell_by_index("scratch/prefix.ipynb", 1, timeout=30.0))

        self.assertTrue(result["ok"])
        updated = json.loads(notebook.read_text(encoding="utf-8"))
        self.assertIsNone(updated["cells"][0]["execution_count"])
        self.assertEqual(updated["cells"][0]["outputs"], [])
        outputs = updated["cells"][1]["outputs"]
        printed = any(
            "42" in tools._join_maybe_list(output.get("text", ""))
            for output in outputs
            if output.get("output_type") == "stream"
        )
        self.assertTrue(printed)


if __name__ == "__main__":
    unittest.main()
