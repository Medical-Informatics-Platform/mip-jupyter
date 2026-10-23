import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mip import agent, cli


class _Variable:
    def __init__(self, code):
        self.code = code

    def summary(self):
        return {"code": self.code, "label": self.code.upper()}


class _Variables:
    def search(self, query):
        return [_Variable(code) for code in ("nihss", "age") if query.lower() in code]


class _DataModel:
    variables = _Variables()

    def summary(self):
        return {"code": "stroke", "version": "3.7", "label": "Stroke"}

    def list_datasets(self):
        return [{"code": "ds1"}, {"code": "ds2"}]

    def list_groups(self):
        return []

    def list_variables(self):
        return [{"code": "nihss"}]


class _Catalog:
    def summaries(self):
        return [{"code": f"model-{i}", "label": "x" * 2000, "secret_extra": "drop me"} for i in range(60)]

    def data_model(self, label, version=None):
        return _DataModel()


class _Algorithm:
    def __init__(self, kind):
        self.kind = kind

    def summary(self):
        return {"label": self.kind, "type": self.kind}


class _Algorithms:
    def list(self):
        return [_Algorithm("statistics"), _Algorithm("model"), _Algorithm("model")]


class _Client:
    def catalog(self):
        return _Catalog()

    def algorithms(self):
        return _Algorithms()


def _run_cli(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = cli.main(list(argv))
    return code, json.loads(out.getvalue())


class TestGuide(unittest.TestCase):
    def test_every_guide_page_and_the_agents_template_are_packaged(self):
        for relative_path in agent.GUIDE_PAGES.values():
            self.assertTrue((agent.DOCS_ROOT / relative_path).is_file(), relative_path)
        self.assertTrue(cli.AGENTS_TEMPLATE.is_file())

    def test_read_guide_topic_narrows_and_missed_topic_falls_back(self):
        matched = agent.read_guide("03-mip-client-api", topic="filters", max_chars=6000)
        unmatched = agent.read_guide("03-mip-client-api", topic="zzzz_nonexistent", max_chars=6000)
        full = agent.read_guide("03-mip-client-api", max_chars=6000)

        self.assertTrue(matched["matched"])
        self.assertIn("F(", matched["content"])
        self.assertLess(len(matched["content"]), len(full["content"]))
        self.assertFalse(unmatched["matched"])
        self.assertEqual(unmatched["content"], full["content"])

    def test_read_guide_rejects_pages_outside_the_allowlist(self):
        with self.assertRaises(ValueError):
            agent.read_guide("../../client")

    def test_read_guide_accepts_wiki_prefix_and_md_suffix(self):
        self.assertEqual(agent.read_guide("wiki/01-onboarding.md")["page"], "01-onboarding")

    def test_list_guide_pages_has_read_when_hints(self):
        pages = {item["page"]: item for item in agent.list_guide_pages()["pages"]}
        self.assertIn("07-pipeline-algorithms", pages)
        self.assertTrue(pages["07-pipeline-algorithms"]["read_when"])

    def test_search_guide_is_bounded(self):
        result = agent.search_guide("logistic regression", limit=2)
        self.assertTrue(result["ok"])
        self.assertLessEqual(len(result["results"]), 2)
        self.assertLessEqual(len(result["results"][0]["snippet"]), agent.MAX_DOC_SNIPPET_CHARS)


class TestEnvStatus(unittest.TestCase):
    def test_nothing_configured_is_not_ready(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True):
            status = agent.env_status(token_dir=Path(tmp))
        self.assertFalse(status["ready"])


class TestMetadataSummaries(unittest.TestCase):
    def test_summaries_are_compact_and_bounded(self):
        with patch("mip.Client.from_env", return_value=_Client()):
            catalog = agent.catalog_summary(limit=100)
            model = agent.data_model_summary("Stroke", include_variables=True)
            variables = agent.search_variables("Stroke", "nih")
            algorithms = agent.algorithm_summary()

        self.assertLessEqual(len(json.dumps(catalog)), agent.MAX_RESPONSE_JSON_CHARS)
        self.assertLessEqual(len(catalog["items"]), agent.MAX_LIST_ITEMS)
        self.assertTrue(catalog["truncated"])
        self.assertNotIn("secret_extra", catalog["items"][0])
        self.assertEqual(model["variables"], [{"code": "nihss"}])
        self.assertEqual([item["code"] for item in variables["items"]], ["nihss"])
        self.assertEqual(algorithms["counts_by_type"], {"statistics": 1, "model": 2})

    def test_errors_are_structured(self):
        with patch("mip.Client.from_env", side_effect=RuntimeError("no backend")):
            result = agent.catalog_summary()
        self.assertEqual(result, {"ok": False, "error_type": "RuntimeError", "error": "no backend"})


class TestCli(unittest.TestCase):
    def test_guide_without_page_lists_pages(self):
        code, result = _run_cli("guide")
        self.assertEqual(code, 0)
        self.assertIn("pages", result)

    def test_guide_unknown_page_fails_cleanly(self):
        code, result = _run_cli("guide", "nope")
        self.assertEqual(code, 1)
        self.assertFalse(result["ok"])

    def test_search_variables_joins_query_words(self):
        with patch.object(agent, "search_variables", return_value={"ok": True}) as search:
            _run_cli("search-variables", "Stroke", "blood", "pressure", "--version", "3.7")
        search.assert_called_once_with("Stroke", "blood pressure", "3.7", agent.DEFAULT_VARIABLE_SEARCH_LIMIT)

    def test_agent_init_writes_files_and_refuses_to_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, output = _run_cli("agent", "init", tmp)
            agents_md = Path(tmp, "AGENTS.md")
            self.assertEqual(code, 0)
            self.assertIn("provider", output["notice"])
            self.assertIn("mip guide", agents_md.read_text(encoding="utf-8"))
            self.assertEqual(Path(tmp, "CLAUDE.md").read_text(encoding="utf-8"), "@AGENTS.md\n")

            agents_md.write_text("mine", encoding="utf-8")
            code, _ = _run_cli("agent", "init", tmp)
            self.assertEqual(code, 1)
            self.assertEqual(agents_md.read_text(encoding="utf-8"), "mine")

            code, _ = _run_cli("agent", "init", tmp, "--force")
            self.assertEqual(code, 0)
            self.assertIn("mip guide", agents_md.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
