"""Bootstrap Codex + Jupyter AI configuration for local and Hub single-user runtimes."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from .jupyter_mcp_config import build_config as build_mcp_config
from .jupyter_mcp_tools import SAFE_JUPYTER_MCP_TOOLS
from .mip_acp_persona import MIP_PERSONA_ID
from .mip_acp_persona import MIP_PERSONA_NAME
from .mip_persona_manager import build_persona_manager_config

# Slim production catalog instructions. Scope/refusal detail: wiki/00 on demand.
MIP_CONTEXT = (
    "MIP federated research: use mip for catalog, cohorts, and analyses."
)

SCOPE_RULES = (
    "MIP notebooks only; refuse off-topic directly (no tools for off-topic); "
    "no invented catalog data."
)

BREVITY_RULES = (
    "Reply concise; summarize run outputs; don't re-read-guide pages already loaded "
    "or paste notebook-visible code."
)

USER_FACING_RULES = (
    "Say MIP platform/connection/catalog/analysis run; hide routes/URLs/env names "
    "unless operator setup is requested."
)

PRIVACY_RULES = (
    "Aggregates only; never expose tokens, identifiers, or row-level data."
)

PROGRESS_RULES = (
    "Explore broadly, compare algorithms, narrow to one hypothesis. "
    "Write the full analysis as ONE scratch .py with # %% markers, then "
    "scratch-to-notebook once; never per-cell fragments. Never re-run a discovery; "
    "update the plan each step. If not converging, stop and ask the user. "
    "Stop once the notebook runs end-to-end."
)

MCP_CLI_RULES = (
    "Shell bridge only: prefix every MCP call with jupyter-mcp "
    "(or python -m mip_jupyter_dev.jupyter_mcp_cli). "
    "Never bare read-guide/scratch-*; never native mcp__*; never edit .ipynb via JSON/fs. "
    "Retry reads once; never retry writes without jupyter-mcp scratch-list/notebook-outline."
)

NATIVE_MCP_RULES = (
    "Native MCP: configured Jupyter MCP tools only; never edit .ipynb via JSON "
    "or filesystem writes."
)

TOOL_PAYLOAD_RULES = (
    "Small JSON args. No write_stdin/heredocs/shell writes. "
    "Notebook is the deliverable: write ONE scratch .py with # %% cell markers "
    "via scratch-write-file, then scratch-to-notebook in one call. "
    "Run cells with run-cell to validate."
)

ROUTING_RULES = (
    "Cold start: skip AGENTS/00/index when intent is clear. "
    "jupyter-mcp read-guide --page PAGE --topic when known "
    "(novel stroke→recipes/stroke-analysis --topic novel; "
    "notebook tools→04-jupyter-mcp --topic payload; "
    "algorithms→07-pipeline-algorithms --topic methods; "
    "env→05-env-and-backend --topic from_env; onboarding→01-onboarding). "
    "index only if unclear; 00-agent-workspace only for refusal/scope. "
    "One guide page per turn. Never find/grep the wiki tree."
)

# Soft budget for production catalog base_instructions (chars). Keep headroom
# for the next rule tweak instead of sitting 47 chars under the limit.
BASE_INSTRUCTIONS_MAX_CHARS = 2000


def build_base_instructions(*, enable_native_jupyter_mcp: bool = False) -> str:
    tool_rules = NATIVE_MCP_RULES if enable_native_jupyter_mcp else MCP_CLI_RULES
    return (
        f"You are {MIP_PERSONA_NAME}. {MIP_CONTEXT} {SCOPE_RULES} "
        f"{USER_FACING_RULES} {PRIVACY_RULES} {PROGRESS_RULES} {tool_rules} "
        f"{TOOL_PAYLOAD_RULES} {ROUTING_RULES} New work under scratch/; "
        f"curated metadata only. {BREVITY_RULES}"
    )


# Local placeholder only (vLLM's default port). Real endpoints come from
# CODEX_VLLM_BASE_URL at runtime; never commit one here.
DEFAULT_CODEX_BASE_URL = "http://127.0.0.1:8000/v1"
# Fallback served id only. Production and CI override it with CODEX_VLLM_MODEL on
# the Hub spawner / container env, so nothing here has to change to switch models.
DEFAULT_CODEX_MODEL = "RadixArk/Qwen3.8-Flash-Next-NVFP4"
# Label shown in the Jupyter AI model picker (the request still sends the served
# slug above). Kept in sync with the persona name by test_codex_bootstrap.
AGENT_MODEL_DISPLAY_NAME = "Cohort Scout"
# Provider id is cosmetic (selects `[model_providers.<id>]` with wire_api=response);
# any OpenAI-compatible /v1/responses server is served under the `vllm` id.
DEFAULT_CODEX_PROVIDER = "vllm"
# Agent window is capped below the served context_length (262144) to limit context bloat.
DEFAULT_CODEX_CONTEXT_WINDOW = 131072
DEFAULT_CODEX_AUTO_COMPACT_LIMIT = 40000
DEFAULT_CODEX_REASONING_EFFORT = "low"
SUPPORTED_CODEX_REASONING_EFFORTS = frozenset({"minimal", "low", "medium"})
DEFAULT_CODEX_PERSONA_ID = MIP_PERSONA_ID
DEFAULT_MCP_PORT = 3001

# Runtime overrides. Every value below is optional; unset means "use the default".
ENV_CODEX_BASE_URL = "CODEX_VLLM_BASE_URL"
ENV_CODEX_MODEL = "CODEX_VLLM_MODEL"
ENV_CODEX_PROVIDER = "CODEX_VLLM_PROVIDER"
ENV_CODEX_CONTEXT_WINDOW = "CODEX_MODEL_CONTEXT_WINDOW"
ENV_CODEX_AUTO_COMPACT_LIMIT = "CODEX_AUTO_COMPACT_TOKEN_LIMIT"
ENV_CODEX_REASONING_EFFORT = "CODEX_REASONING_EFFORT"


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return int(value.strip())
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {value!r}.") from exc


def normalize_codex_base_url(base_url: str) -> str:
    """Trim whitespace and trailing slashes so `{base_url}/responses` stays valid."""
    url = base_url.strip().rstrip("/")
    if not url:
        raise ValueError(
            "CODEX_VLLM_BASE_URL must be a reachable OpenAI-compatible base URL ending in /v1."
        )
    return url


def _active_reasoning_effort() -> str:
    effort = os.getenv(ENV_CODEX_REASONING_EFFORT, DEFAULT_CODEX_REASONING_EFFORT).strip().lower()
    if effort not in SUPPORTED_CODEX_REASONING_EFFORTS:
        supported = ", ".join(sorted(SUPPORTED_CODEX_REASONING_EFFORTS))
        raise ValueError(f"{ENV_CODEX_REASONING_EFFORT} must be one of: {supported}.")
    return effort


@dataclass(frozen=True)
class CodexSettings:
    base_url: str
    model: str
    catalog_models: tuple[str, ...]
    provider: str
    context_window: int
    auto_compact_limit: int
    reasoning_effort: str
    mcp_port: int
    enable_native_jupyter_mcp: bool

    @classmethod
    def resolve(
        cls,
        *,
        base_url: str,
        model: str,
        provider: str,
        context_window: int | None = None,
        auto_compact_limit: int | None = None,
        reasoning_effort: str | None = None,
        mcp_port: int | None = None,
        enable_native_jupyter_mcp: bool = False,
    ) -> CodexSettings:
        """Build settings from explicit values with env normalization and validation."""
        active_model = model.strip() or DEFAULT_CODEX_MODEL
        return cls(
            base_url=normalize_codex_base_url(base_url),
            model=active_model,
            catalog_models=(active_model,),
            provider=provider.strip() or DEFAULT_CODEX_PROVIDER,
            context_window=(
                context_window
                if context_window is not None
                else _env_int(ENV_CODEX_CONTEXT_WINDOW, DEFAULT_CODEX_CONTEXT_WINDOW)
            ),
            auto_compact_limit=(
                auto_compact_limit
                if auto_compact_limit is not None
                else _env_int(ENV_CODEX_AUTO_COMPACT_LIMIT, DEFAULT_CODEX_AUTO_COMPACT_LIMIT)
            ),
            reasoning_effort=reasoning_effort or _active_reasoning_effort(),
            mcp_port=mcp_port if mcp_port is not None else int(os.getenv("JUPYTER_MCP_PORT", str(DEFAULT_MCP_PORT))),
            enable_native_jupyter_mcp=enable_native_jupyter_mcp,
        )

    @classmethod
    def from_env(
        cls,
        *,
        mcp_port: int | None = None,
    ) -> CodexSettings:
        return cls.resolve(
            base_url=os.getenv(ENV_CODEX_BASE_URL, DEFAULT_CODEX_BASE_URL),
            model=os.getenv(ENV_CODEX_MODEL, DEFAULT_CODEX_MODEL),
            provider=os.getenv(ENV_CODEX_PROVIDER, DEFAULT_CODEX_PROVIDER),
            mcp_port=mcp_port,
            enable_native_jupyter_mcp=_env_flag("CODEX_ENABLE_NATIVE_JUPYTER_MCP"),
        )


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _catalog_entry(
    slug: str,
    *,
    context_window: int,
    base_instructions: str,
    reasoning_effort: str,
    priority: int,
) -> dict:
    return {
        "slug": slug,
        "display_name": AGENT_MODEL_DISPLAY_NAME,
        "description": (
            f"{AGENT_MODEL_DISPLAY_NAME} on {slug} "
            "via an OpenAI-compatible /v1/responses endpoint."
        ),
        "default_reasoning_level": reasoning_effort,
        "supported_reasoning_levels": [
            {
                "effort": "minimal",
                "description": "Fast local inference with minimal reasoning.",
            },
            {
                "effort": "low",
                "description": "Light reasoning for coding and notebook assistance.",
            },
            {
                "effort": "medium",
                "description": "Deeper reasoning for multi-step exploration and audits.",
            },
        ],
        "shell_type": "shell_command",
        "visibility": "list",
        "supported_in_api": True,
        "priority": priority,
        "additional_speed_tiers": [],
        "service_tiers": [],
        "availability_nux": None,
        "upgrade": None,
        "base_instructions": base_instructions,
        "supports_reasoning_summaries": False,
        "default_reasoning_summary": "none",
        "support_verbosity": False,
        "default_verbosity": "low",
        "apply_patch_tool_type": None,
        "web_search_tool_type": "text_and_image",
        "truncation_policy": {"mode": "tokens", "limit": 10000},
        "supports_parallel_tool_calls": False,
        "supports_image_detail_original": False,
        "context_window": context_window,
        "max_context_window": context_window,
        "effective_context_window_percent": 95,
        "experimental_supported_tools": [],
        "input_modalities": ["text"],
        "supports_search_tool": False,
        # The Responses path needs full tool payloads; lite mode returns
        # plain text instead of shell/function_call items.
        "use_responses_lite": False,
    }


def write_codex_model_catalog(path: Path, settings: CodexSettings) -> None:
    """Write the Codex catalog; the active served id is the first (and only) entry."""

    base_instructions = build_base_instructions(
        enable_native_jupyter_mcp=settings.enable_native_jupyter_mcp
    )
    entries = [
        _catalog_entry(
            slug,
            context_window=settings.context_window,
            base_instructions=base_instructions,
            reasoning_effort=settings.reasoning_effort,
            priority=index,
        )
        for index, slug in enumerate(settings.catalog_models)
    ]
    _write_json(path, {"models": entries})


def write_codex_acp_wrapper(path: Path, executable: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    script = (
        "#!/bin/sh\n"
        f"exec {shlex.quote(executable)} "
        "-c 'approval_policy=\"never\"' "
        "-c 'sandbox_mode=\"danger-full-access\"' "
        "-c 'shell_environment_policy.inherit=\"all\"' "
        "\"$@\"\n"
    )
    path.write_text(script, encoding="utf-8")
    path.chmod(0o755)


def write_jupyter_mcp_cli_wrapper(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Use the active interpreter; bare `python` is often missing on Linux hosts.
    script = f"#!/bin/sh\nexec {shlex.quote(sys.executable)} -m mip_jupyter_dev.jupyter_mcp_cli \"$@\"\n"
    path.write_text(script, encoding="utf-8")
    path.chmod(0o755)


def write_shell_guard_wrapper(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    script = (
        "#!/bin/sh\n"
        "validate_command_args() {\n"
        "  while [ $# -gt 0 ]; do\n"
        "    case \"$1\" in\n"
        "      -c|-[!-]*c*)\n"
        "        [ -n \"$2\" ] || return 0\n"
        "        python -m mip_jupyter_dev.shell_guard --validate \"$2\"\n"
        "        return $?\n"
        "        ;;\n"
        "    esac\n"
        "    shift\n"
        "  done\n"
        "}\n"
        "validate_command_args \"$@\" || exit 1\n"
        "exec /bin/bash \"$@\"\n"
    )
    path.write_text(script, encoding="utf-8")
    path.chmod(0o755)


def write_codex_config(path: Path, settings: CodexSettings, model_catalog_path: Path) -> None:
    provider = settings.provider
    mcp_server_config = ""
    if settings.enable_native_jupyter_mcp:
        mcp_server_config = (
            "\n[mcp_servers.\"Jupyter MCP Server\"]\n"
            f'url = "http://127.0.0.1:{settings.mcp_port}/mcp"\n'
        )
    config = (
        f'model = "{settings.model}"\n'
        f'model_provider = "{provider}"\n'
        f'model_catalog_json = "{model_catalog_path}"\n'
        f"model_context_window = {settings.context_window}\n"
        f"model_auto_compact_token_limit = {settings.auto_compact_limit}\n"
        f'model_reasoning_effort = "{settings.reasoning_effort}"\n'
        'model_reasoning_summary = "none"\n'
        "model_supports_reasoning_summaries = false\n"
        'approval_policy = "never"\n'
        'sandbox_mode = "danger-full-access"\n'
        'model_verbosity = "low"\n'
        'web_search = "disabled"\n\n'
        "[shell_environment_policy]\n"
        'inherit = "all"\n'
        "ignore_default_excludes = false\n"
        'exclude = ["*PASSWORD*", "*TOKEN*", "*SECRET*", "*COOKIE*", "*SESSION*"]\n\n'
        "[features]\n"
        "multi_agent = false\n\n"
        f"[model_providers.{provider}]\n"
        'name = "vLLM"\n'
        f'base_url = "{settings.base_url}"\n'
        'wire_api = "responses"\n'
        f"{mcp_server_config}"
    )
    path.write_text(config, encoding="utf-8")


def build_jupyter_ai_config(settings: CodexSettings) -> dict:
    if settings.enable_native_jupyter_mcp:
        builtin_mcp_servers: list | None = None
    else:
        builtin_mcp_servers = []
    config = build_mcp_config(mcp_port=settings.mcp_port)
    config.update(
        build_persona_manager_config(
            default_persona_id=DEFAULT_CODEX_PERSONA_ID,
            builtin_mcp_servers=builtin_mcp_servers,
        )
    )
    config["MCPExtensionApp"]["mcp_tools"] = SAFE_JUPYTER_MCP_TOOLS
    return config


def bootstrap_codex(
    codex_home: Path,
    jupyter_ai_config: Path,
    settings: CodexSettings,
) -> Path | None:
    """Write Codex and Jupyter AI config. Returns codex-acp wrapper bin dir for PATH."""
    codex_home.mkdir(parents=True, exist_ok=True)
    model_catalog_path = codex_home / "model-catalog.json"
    write_codex_model_catalog(model_catalog_path, settings)
    write_codex_config(codex_home / "config.toml", settings, model_catalog_path)

    jupyter_ai_config.parent.mkdir(parents=True, exist_ok=True)
    _write_json(jupyter_ai_config, build_jupyter_ai_config(settings))

    write_jupyter_mcp_cli_wrapper(codex_home / "bin" / "jupyter-mcp")
    write_shell_guard_wrapper(codex_home / "bin" / "mip-shell-guard")

    codex_acp_path = shutil.which("codex-acp")
    if not codex_acp_path:
        return codex_home / "bin"
    wrapper = codex_home / "bin" / "codex-acp"
    write_codex_acp_wrapper(wrapper, codex_acp_path)
    return wrapper.parent


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bootstrap Codex + Jupyter AI for mip-jupyter.")
    parser.add_argument("codex_home", help="Directory for CODEX_HOME (config.toml, catalog)")
    parser.add_argument("jupyter_ai_config", help="Output JupyterLab JSON config path")
    parser.add_argument("--mcp-port", type=int, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not os.getenv("CODEX_VLLM_BASE_URL"):
        raise SystemExit("CODEX_VLLM_BASE_URL must be set to bootstrap Codex.")
    settings = CodexSettings.from_env(mcp_port=args.mcp_port)
    wrapper_bin = bootstrap_codex(Path(args.codex_home), Path(args.jupyter_ai_config), settings)
    if wrapper_bin is None:
        print("warning: codex-acp not found on PATH; Jupyter AI Codex persona may not start", flush=True)
    else:
        print(f"codex-acp wrapper: {wrapper_bin / 'codex-acp'}", flush=True)
    print(f"CODEX_HOME={args.codex_home}", flush=True)
    print(f"Jupyter AI config: {args.jupyter_ai_config}", flush=True)
    print(f"Codex base_url: {settings.base_url}", flush=True)
    print(f"Codex model: {settings.model}", flush=True)
    print(f"Codex reasoning effort: {settings.reasoning_effort}", flush=True)
    print(f"Codex catalog models: {', '.join(settings.catalog_models)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
