"""Tests for Codex bootstrap and vLLM model catalog generation."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from traitlets.utils.importstring import import_item

from dev import notebook as notebook_runner
from dev.codex_bootstrap import (
    AGENT_MODEL_DISPLAY_NAME,
    BASE_INSTRUCTIONS_MAX_CHARS,
    DEFAULT_CODEX_MODEL,
    DEFAULT_CODEX_PERSONA_ID,
    DEFAULT_CODEX_REASONING_EFFORT,
    MCP_CLI_RULES,
    NATIVE_MCP_RULES,
    PRIVACY_RULES,
    ROUTING_RULES,
    SCOPE_RULES,
    TOOL_PAYLOAD_RULES,
    CodexSettings,
    bootstrap_codex,
    build_base_instructions,
    write_codex_config,
    write_codex_model_catalog,
)
from dev.mip_acp_persona import MIP_PERSONA_ID
from dev.mip_acp_persona import MIP_PERSONA_NAME
from dev.mip_acp_persona import TOOL_CALL_PARSE_ERROR_MESSAGE
from dev.mip_acp_persona import VLLM_UNAVAILABLE_MESSAGE
from dev.mip_acp_persona import CohortScoutPersona
from dev.mip_acp_persona import is_tool_call_parse_error
from dev.mip_acp_persona import is_vllm_unavailable_error
from dev.mip_persona_manager import (
    ALLOWED_PERSONA_ENTRY_POINTS,
    MIP_PERSONA_MANAGER_CLASS,
    MipPersonaManager,
)
from dev.jupyter_mcp_config import build_config as build_mcp_config
from dev import jupyter_mcp_cli


@pytest.fixture(autouse=True)
def _clear_codex_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "CODEX_VLLM_BASE_URL",
        "CODEX_VLLM_MODEL",
        "CODEX_VLLM_PROVIDER",
        "CODEX_REASONING_EFFORT",
        "CODEX_MODEL_CONTEXT_WINDOW",
        "CODEX_AUTO_COMPACT_TOKEN_LIMIT",
        "CODEX_ENABLE_NATIVE_JUPYTER_MCP",
    ):
        monkeypatch.delenv(name, raising=False)


def test_from_env_default_model_is_served_id() -> None:
    settings = CodexSettings.from_env()
    assert settings.base_url == "http://127.0.0.1:8000/v1"
    assert settings.model == "RadixArk/Qwen3.8-Flash-Next-NVFP4"
    assert settings.catalog_models == ("RadixArk/Qwen3.8-Flash-Next-NVFP4",)
    assert settings.context_window == 131072
    assert settings.auto_compact_limit == 40000
    assert settings.reasoning_effort == "low"
    assert not settings.enable_native_jupyter_mcp


def test_native_mcp_can_be_enabled_by_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CODEX_ENABLE_NATIVE_JUPYTER_MCP", "1")
    settings = CodexSettings.from_env()
    assert settings.enable_native_jupyter_mcp


def test_env_budget_overrides_apply_to_catalog(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CODEX_VLLM_MODEL", "acme/Brand-New-Model")
    monkeypatch.setenv("CODEX_MODEL_CONTEXT_WINDOW", "65536")
    monkeypatch.setenv("CODEX_AUTO_COMPACT_TOKEN_LIMIT", "50000")
    settings = CodexSettings.from_env()
    assert settings.context_window == 65536
    assert settings.auto_compact_limit == 50000

    catalog_path = tmp_path / "model-catalog.json"
    write_codex_model_catalog(catalog_path, settings)

    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    assert len(catalog["models"]) == 1
    entry = catalog["models"][0]
    assert entry["slug"] == "acme/Brand-New-Model"
    assert entry["display_name"] == AGENT_MODEL_DISPLAY_NAME
    assert "acme/Brand-New-Model" in entry["description"]
    assert entry["context_window"] == 65536


def test_base_url_is_normalized_and_catalog_pins_active_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CODEX_VLLM_BASE_URL", "http://10.0.0.5:8000/v1/")
    settings = CodexSettings.from_env()

    assert settings.base_url == "http://10.0.0.5:8000/v1"
    assert settings.catalog_models == (DEFAULT_CODEX_MODEL,)


def test_invalid_base_url_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CODEX_VLLM_BASE_URL", "   ")
    with pytest.raises(ValueError, match="CODEX_VLLM_BASE_URL"):
        CodexSettings.from_env()


def test_from_env_invalid_reasoning_effort_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CODEX_REASONING_EFFORT", "xhigh")
    with pytest.raises(ValueError, match="CODEX_REASONING_EFFORT"):
        CodexSettings.from_env()


def test_model_catalog_contains_single_served_model(tmp_path: Path) -> None:
    settings = CodexSettings.from_env()
    catalog_path = tmp_path / "model-catalog.json"
    write_codex_model_catalog(catalog_path, settings)

    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    slugs = [entry["slug"] for entry in catalog["models"]]
    assert slugs == ["RadixArk/Qwen3.8-Flash-Next-NVFP4"]

    assert catalog["models"][0]["display_name"] == AGENT_MODEL_DISPLAY_NAME
    assert MIP_PERSONA_NAME == AGENT_MODEL_DISPLAY_NAME

    model = catalog["models"][0]
    assert model["context_window"] == 131072
    assert model["default_reasoning_level"] == "low"
    assert {level["effort"] for level in model["supported_reasoning_levels"]} == {
        "minimal",
        "low",
        "medium",
    }
    assert "recipes/stroke-analysis" in model["base_instructions"]
    assert "--topic" in model["base_instructions"]
    assert "skip AGENTS" in model["base_instructions"]
    assert SCOPE_RULES in model["base_instructions"]
    assert MCP_CLI_RULES in model["base_instructions"]
    assert TOOL_PAYLOAD_RULES in model["base_instructions"]
    assert PRIVACY_RULES in model["base_instructions"]
    assert ROUTING_RULES in model["base_instructions"]
    assert "available_algorithms" not in model["base_instructions"]
    assert "write_stdin" in model["base_instructions"]
    assert "Subcommands:" not in model["base_instructions"]
    assert "never native mcp__*" in model["base_instructions"]
    assert "never retry writes" in model["base_instructions"]
    assert len(model["base_instructions"]) <= BASE_INSTRUCTIONS_MAX_CHARS
    assert len(build_base_instructions()) <= BASE_INSTRUCTIONS_MAX_CHARS


def test_native_model_instructions_allow_native_mcp(tmp_path: Path) -> None:
    settings = replace(CodexSettings.from_env(), enable_native_jupyter_mcp=True)
    catalog_path = tmp_path / "model-catalog.json"
    write_codex_model_catalog(catalog_path, settings)
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))

    instructions = catalog["models"][0]["base_instructions"]
    assert NATIVE_MCP_RULES in instructions
    assert MCP_CLI_RULES not in instructions
    assert "never native mcp__*" not in instructions


def test_config_toml_uses_default_served_model(tmp_path: Path) -> None:
    settings = CodexSettings.from_env()
    catalog_path = tmp_path / "model-catalog.json"
    config_path = tmp_path / "config.toml"
    write_codex_model_catalog(catalog_path, settings)
    write_codex_config(config_path, settings, catalog_path)

    config = config_path.read_text(encoding="utf-8")
    assert 'model = "RadixArk/Qwen3.8-Flash-Next-NVFP4"' in config
    assert "model_context_window = 131072" in config
    assert "model_auto_compact_token_limit = 40000" in config
    assert 'model_reasoning_effort = "low"' in config
    assert '[mcp_servers."Jupyter MCP Server"]' not in config


def test_native_config_registers_jupyter_mcp_server(tmp_path: Path) -> None:
    settings = replace(CodexSettings.from_env(), enable_native_jupyter_mcp=True)
    config_path = tmp_path / "config.toml"
    write_codex_config(config_path, settings, tmp_path / "model-catalog.json")

    config = config_path.read_text(encoding="utf-8")
    assert '[mcp_servers."Jupyter MCP Server"]' in config
    assert 'url = "http://127.0.0.1:3001/mcp"' in config


def test_read_guide_cli_routes_to_allowlisted_page() -> None:
    args = jupyter_mcp_cli._parser().parse_args(
        [
            "read-guide",
            "--page",
            "05-env-and-backend",
            "--topic",
            "Client.from_env",
        ]
    )
    name, arguments = jupyter_mcp_cli._tool_call_for_args(args)
    assert name == "agent_read_guide"
    assert arguments == {
            "topic": "Client.from_env",
            "page": "05-env-and-backend",
            "max_chars": jupyter_mcp_cli.tools.DEFAULT_WIKI_MAX_CHARS,
        }


def test_notebook_cli_context_overrides_are_used() -> None:
    args = notebook_runner._parser().parse_args(
        [
            "--mcp-port",
            "3123",
            "--codex-context-window",
            "4096",
            "--codex-auto-compact-limit",
            "3500",
        ]
    )

    settings = notebook_runner._codex_settings_from_args(args)

    assert settings.model == "RadixArk/Qwen3.8-Flash-Next-NVFP4"
    assert settings.catalog_models == ("RadixArk/Qwen3.8-Flash-Next-NVFP4",)
    assert settings.context_window == 4096
    assert settings.auto_compact_limit == 3500


def test_notebook_cli_codex_model_and_url_flags_are_used() -> None:
    args = notebook_runner._parser().parse_args(
        [
            "--codex-base-url",
            "http://127.0.0.1:8001/v1/",
            "--codex-model",
            "acme/Brand-New-Model",
        ]
    )

    settings = notebook_runner._codex_settings_from_args(args)

    assert settings.base_url == "http://127.0.0.1:8001/v1"
    assert settings.model == "acme/Brand-New-Model"
    assert settings.catalog_models == ("acme/Brand-New-Model",)


def test_notebook_cli_defaults_honor_env_budgets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CODEX_MODEL_CONTEXT_WINDOW", "65536")
    monkeypatch.setenv("CODEX_AUTO_COMPACT_TOKEN_LIMIT", "30000")

    args = notebook_runner._parser().parse_args([])

    settings = notebook_runner._codex_settings_from_args(args)
    assert settings.context_window == 65536
    assert settings.auto_compact_limit == 30000


def test_sanitize_path_drops_error_text_and_keeps_essentials() -> None:
    cleaned = notebook_runner._sanitize_path(
        '/tmp/x/bin:Unknown command: "bin":/usr/games',
        prepend=Path("/tmp/codex/bin"),
    )
    assert cleaned.startswith("/tmp/codex/bin:")
    assert "Unknown" not in cleaned
    assert "/usr/bin" in cleaned.split(":")
    assert "/bin" in cleaned.split(":")


def test_vllm_unavailable_detection_matches_connection_failures() -> None:
    assert is_vllm_unavailable_error(ConnectionError("connection refused"))
    assert is_vllm_unavailable_error(RuntimeError("503 Service Unavailable from vLLM"))
    assert is_vllm_unavailable_error(TimeoutError("request timed out"))
    assert not is_vllm_unavailable_error(ValueError("invalid notebook path"))


def test_tool_call_parse_errors_are_not_treated_as_vllm_outage() -> None:
    error_text = (
        '{"error":{"message":"Expecting \',\' delimiter: line 1 column 3716",'
        '"type":"BadRequestError","code":400}}'
    )
    assert is_tool_call_parse_error(RuntimeError(error_text))
    assert not is_vllm_unavailable_error(RuntimeError(error_text))
    assert is_tool_call_parse_error(RuntimeError("failed to parse function arguments: invalid number"))


class _ErrorWithData(Exception):
    def __init__(self, message: str, data: str) -> None:
        super().__init__(message)
        self.data = data


def test_tool_call_parse_error_detects_exception_data_field() -> None:
    err = _ErrorWithData("request failed", '{"message":"Expecting \',\' delimiter"}')
    assert is_tool_call_parse_error(err)
    assert not is_vllm_unavailable_error(err)


@pytest.mark.asyncio
async def test_cohort_scout_handle_tool_call_parse_error_sends_user_message() -> None:
    persona = CohortScoutPersona.__new__(CohortScoutPersona)
    import logging

    persona.log = logging.getLogger("test")
    sent: list[str] = []
    persona.send_message = sent.append  # type: ignore[method-assign]

    await CohortScoutPersona.handle_tool_call_parse_error(
        persona,
        RuntimeError("Expecting ',' delimiter: line 1 column 3716"),
    )
    assert sent == [TOOL_CALL_PARSE_ERROR_MESSAGE]


def test_tool_call_parse_error_message_mentions_small_steps() -> None:
    assert "new chat" in TOOL_CALL_PARSE_ERROR_MESSAGE.lower()
    assert "scratch-write-file" in TOOL_CALL_PARSE_ERROR_MESSAGE.lower()
    assert "scratch-list" in TOOL_CALL_PARSE_ERROR_MESSAGE.lower()
    assert "notebook-outline" in TOOL_CALL_PARSE_ERROR_MESSAGE.lower()


def test_vllm_unavailable_message_is_user_facing() -> None:
    assert "Cohort Scout cannot reach the vLLM model service" in VLLM_UNAVAILABLE_MESSAGE
    assert "MIP platform connection are unaffected" in VLLM_UNAVAILABLE_MESSAGE
    assert "CODEX_VLLM_BASE_URL" in VLLM_UNAVAILABLE_MESSAGE


def test_default_persona_is_cohort_scout() -> None:
    assert DEFAULT_CODEX_PERSONA_ID == MIP_PERSONA_ID
    assert MIP_PERSONA_NAME == "Cohort Scout"


def test_persona_manager_class_is_importable() -> None:
    assert import_item(MIP_PERSONA_MANAGER_CLASS) is MipPersonaManager


def test_bootstrap_codex_writes_catalog_and_config(tmp_path: Path) -> None:
    settings = CodexSettings.from_env()
    codex_home = tmp_path / "codex-home"
    jupyter_config = tmp_path / "jupyter_ai_config.json"

    bootstrap_codex(codex_home, jupyter_config, settings)

    catalog = json.loads((codex_home / "model-catalog.json").read_text(encoding="utf-8"))
    assert len(catalog["models"]) == 1
    assert catalog["models"][0]["slug"] == "RadixArk/Qwen3.8-Flash-Next-NVFP4"
    assert MIP_PERSONA_NAME in catalog["models"][0]["base_instructions"]
    assert (codex_home / "config.toml").is_file()
    jupyter_mcp_wrapper = codex_home / "bin" / "jupyter-mcp"
    assert jupyter_mcp_wrapper.is_file()
    assert jupyter_mcp_wrapper.read_text(encoding="utf-8").startswith("#!/bin/sh")
    shell_guard = codex_home / "bin" / "mip-shell-guard"
    assert shell_guard.is_file()
    assert shell_guard.read_text(encoding="utf-8").startswith("#!/bin/sh")
    jupyter_config_data = json.loads(jupyter_config.read_text(encoding="utf-8"))
    assert jupyter_config_data["PersonaManager"]["default_persona_id"] == MIP_PERSONA_ID
    assert jupyter_config_data["PersonaManager"]["builtin_mcp_servers"] == []
    assert (
        jupyter_config_data["PersonaManagerExtension"]["persona_manager_class"]
        == MIP_PERSONA_MANAGER_CLASS
    )
    assert jupyter_config.is_file()


def test_mcp_config_uses_mip_persona_manager_only() -> None:
    config = build_mcp_config(mcp_port=3001)
    assert config["PersonaManager"]["default_persona_id"] == MIP_PERSONA_ID
    assert config["PersonaManagerExtension"]["persona_manager_class"] == MIP_PERSONA_MANAGER_CLASS


def test_mip_persona_manager_filters_third_party_entry_points(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from jupyter_ai_persona_manager.persona_manager import PersonaManager

    PersonaManager._ep_persona_classes = None

    def fake_load_all(_self) -> None:
        PersonaManager._ep_persona_classes = [
            {"module": "codex-acp", "persona_class": object(), "traceback": None},
            {"module": "claude-acp", "persona_class": object(), "traceback": None},
            {"module": "cohort-scout", "persona_class": object(), "traceback": None},
        ]

    monkeypatch.setattr(PersonaManager, "_init_ep_persona_classes", fake_load_all)

    manager = MipPersonaManager.__new__(MipPersonaManager)
    import logging

    manager.log = logging.getLogger("test")
    MipPersonaManager._init_ep_persona_classes(manager)

    loaded = PersonaManager._ep_persona_classes or []
    assert [item["module"] for item in loaded] == ["cohort-scout"]
    assert ALLOWED_PERSONA_ENTRY_POINTS == frozenset({"cohort-scout"})
    PersonaManager._ep_persona_classes = None
