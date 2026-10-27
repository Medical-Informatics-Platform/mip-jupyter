import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mip import agent, cli
from mip.exceptions import MipConfigurationError


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
    def test_remote_setup_counts_only_mip_login(self):
        # Client.from_env() ignores the others on the MIP_URL path, so they must not count.
        env = {
            "MIP_URL": "https://mip.example/",
            "MIP_TOKEN": "x",
            "JUPYTERHUB_API_URL": "https://mip.example/notebook/hub/api",
            "JUPYTERHUB_API_TOKEN": "x",
        }
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, env, clear=True):
            credentials = Path(tmp, "credentials.json")
            (Path(tmp) / "mip_token").write_text("leftover", encoding="utf-8")
            with patch("mip.keycloak.CREDENTIALS_FILE", credentials):
                self.assertFalse(agent.env_status(token_dir=Path(tmp))["ready"])
                credentials.write_text(
                    json.dumps({"https://mip.example": {"refresh_token": "TOP_SECRET"}}), encoding="utf-8"
                )
                status = agent.env_status(token_dir=Path(tmp))
        self.assertTrue(status["ready"])
        self.assertNotIn("TOP_SECRET", json.dumps(status))

    def test_remembered_portal_counts_without_mip_url(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True):
            credentials = Path(tmp, "credentials.json")
            credentials.write_text(
                json.dumps({"https://mip.example": {"refresh_token": "TOP_SECRET"}, "default": "https://mip.example"}),
                encoding="utf-8",
            )
            with patch("mip.keycloak.CREDENTIALS_FILE", credentials):
                status = agent.env_status(token_dir=Path(tmp))
        self.assertTrue(status["ready"])
        self.assertNotIn("TOP_SECRET", json.dumps(status))

    def test_remote_setup_counts_mip_api_token(self):
        env = {"MIP_URL": "https://mip.example", "MIP_API_TOKEN": "TOP_SECRET"}
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, env, clear=True), patch(
            "mip.keycloak.CREDENTIALS_FILE", Path(tmp, "credentials.json")
        ):
            status = agent.env_status(token_dir=Path(tmp))
        self.assertTrue(status["ready"])
        self.assertNotIn("TOP_SECRET", json.dumps(status))

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

    def test_login_needs_a_portal(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True), patch(
            "mip.keycloak.CREDENTIALS_FILE", Path(tmp, "credentials.json")
        ):
            code, result = _run_cli("login")
        self.assertEqual(code, 1)
        self.assertIn("mip login https://", result["error"])

    def test_login_takes_the_portal_as_argument(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True), patch(
            "mip.keycloak.CREDENTIALS_FILE", Path(tmp, "credentials.json")
        ), patch("mip.keycloak.login", return_value={"ok": True}) as login, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(_run_cli("login", "https://mip.example/")[0], 0)
        self.assertEqual(login.call_args.args, ("https://mip.example", "https://mip.example/services"))

    def test_login_shows_instructions_on_stderr_and_json_on_stdout(self):
        def fake_login(mip_url, backend_url, *, show):
            show("open https://idp.example/device")
            return {"ok": True, "signed_in_to": mip_url}

        err = io.StringIO()
        with patch.dict(os.environ, {"MIP_URL": "https://mip.example/"}, clear=True), patch(
            "mip.keycloak.login", side_effect=fake_login
        ) as login, contextlib.redirect_stderr(err):
            code, result = _run_cli("login")
        self.assertEqual(code, 0)
        self.assertEqual(result["signed_in_to"], "https://mip.example")
        self.assertIn("idp.example/device", err.getvalue())
        self.assertEqual(login.call_args.args, ("https://mip.example", "https://mip.example/services"))

    def test_login_token_pastes_hidden_and_saves(self):
        with patch.dict(os.environ, {"MIP_URL": "https://mip.example"}, clear=True), patch(
            "getpass.getpass", return_value=" pasted \n"
        ), patch("mip.keycloak.save_token", return_value={"ok": True}) as save:
            self.assertEqual(_run_cli("login", "--token"), (0, {"ok": True}))
        save.assert_called_once_with("https://mip.example", "https://mip.example/services", "pasted")
        with patch.dict(os.environ, {"MIP_URL": "https://mip.example"}, clear=True), patch(
            "getpass.getpass", return_value=""
        ):
            self.assertEqual(_run_cli("login", "--token")[0], 1)

    def test_sign_in_errors_are_json(self):
        with patch.dict(os.environ, {"MIP_URL": "https://mip.example"}, clear=True), patch(
            "mip.keycloak.logout", side_effect=MipConfigurationError("no")
        ):
            self.assertEqual(_run_cli("logout"), (1, {"ok": False, "error": "no"}))

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
