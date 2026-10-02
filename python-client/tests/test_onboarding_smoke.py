"""Smoke checks for onboarding notebook and user docs."""

from __future__ import annotations

import ast
import json
import re
import unittest
from pathlib import Path

import mip
from mip.display import HelpText


REPO_ROOT = Path(__file__).resolve().parents[2]


def _python_blocks(markdown: str) -> list[str]:
    blocks = []
    pattern = re.compile(r"```python\n(.*?)```", re.DOTALL)
    for match in pattern.finditer(markdown):
        blocks.append(match.group(1))
    return blocks


def _assigned_names(source: str) -> set[str]:
    names: set[str] = set()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
    return names


def _used_names(source: str) -> set[str]:
    names: set[str] = set()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            names.add(node.id)
    return names


class TestOnboardingSmoke(unittest.TestCase):
    def test_public_exports_include_to_frame(self):
        self.assertIn("to_frame", mip.__all__)

    def test_help_returns_help_text_without_printing(self):
        from mip.display import show_help

        help_obj = show_help("DataModel")
        self.assertIsInstance(help_obj, HelpText)
        self.assertIn("DataModel help", str(help_obj))
        self.assertIn("DataModel help", help_obj._repr_html_())

    def test_how_to_choose_example_defines_names_before_use(self):
        text = (REPO_ROOT / "docs/user/how-to-choose.md").read_text(encoding="utf-8")
        blocks = _python_blocks(text)
        self.assertTrue(blocks, "expected at least one python code block")

        flow_block = max(blocks, key=len)
        assigned = _assigned_names(flow_block)
        used = _used_names(flow_block)
        builtins = set(dir(__builtins__)) if isinstance(__builtins__, dict) else set(dir(__builtins__))
        undefined = {
            name
            for name in used
            if name not in assigned
            and name not in builtins
            and name not in {"mip", "display", "F", "MissingValuesHandler", "OutlierWinsorizer"}
        }
        # Allow attribute-style roots that are imported or assigned earlier in the block.
        allowed_roots = {"client", "catalog", "dm", "age", "adni", "mmse", "analysis_set", "pipeline"}
        unexpected = {name for name in undefined if name not in allowed_roots}
        self.assertEqual(unexpected, set(), f"undefined names in how-to-choose flow: {unexpected}")

    def test_welcome_notebook_discovery_cells_use_display(self):
        nb = json.loads((REPO_ROOT / "workspace/Welcome.ipynb").read_text(encoding="utf-8"))
        code_cells = [cell for cell in nb["cells"] if cell.get("cell_type") == "code"]
        discovery_sources = "\n".join(
            "".join(cell.get("source", []))
            for cell in code_cells
            if "catalog.data_model" in "".join(cell.get("source", []))
            or "dm.variables.search" in "".join(cell.get("source", []))
            or "client.algorithms()" in "".join(cell.get("source", []))
            or "display(analysis_set)" in "".join(cell.get("source", []))
            or "display(pipeline)" in "".join(cell.get("source", []))
        )
        self.assertIn("from IPython.display import display", "".join(code_cells[0]["source"]))
        self.assertGreaterEqual(discovery_sources.count("display("), 8)

    def test_welcome_notebook_has_no_stale_cached_outputs(self):
        nb = json.loads((REPO_ROOT / "workspace/Welcome.ipynb").read_text(encoding="utf-8"))
        for cell in nb["cells"]:
            if cell.get("cell_type") != "code":
                continue
            self.assertEqual(cell.get("outputs", []), [])
            self.assertIsNone(cell.get("execution_count"))


if __name__ == "__main__":
    unittest.main()
