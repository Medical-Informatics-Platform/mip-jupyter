"""Start local JupyterLab with Codex configured for mip-jupyter."""

from __future__ import annotations

import argparse
import errno
import os
import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

from .codex_bootstrap import (
    DEFAULT_CODEX_BASE_URL,
    DEFAULT_CODEX_MODEL,
    DEFAULT_CODEX_PROVIDER,
    DEFAULT_CODEX_CONTEXT_WINDOW,
    DEFAULT_CODEX_AUTO_COMPACT_LIMIT,
    DEFAULT_CODEX_REASONING_EFFORT,
    DEFAULT_MCP_PORT,
    ENV_CODEX_AUTO_COMPACT_LIMIT,
    ENV_CODEX_BASE_URL,
    ENV_CODEX_CONTEXT_WINDOW,
    ENV_CODEX_MODEL,
    CodexSettings,
    _env_flag,
    bootstrap_codex,
)
from .mip_acp_persona import MIP_PERSONA_NAME


DEFAULT_BACKEND_URL = "http://127.0.0.1:8080/services"
DEFAULT_TOKEN = "dev"
# Paths are relative to ServerApp.root_dir (= workspace/), matching production.
DEFAULT_NOTEBOOK = "examples/feres_analysis.ipynb"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8888


def _notebook_under_workspace(notebook: str) -> str:
    """Normalize Lab tree paths; strip a leading workspace/ from older env values."""
    normalized = notebook.replace("\\", "/").lstrip("/")
    if normalized == "workspace" or normalized.startswith("workspace/"):
        return normalized[len("workspace") :].lstrip("/")
    return normalized


def _sanitize_path(path_value: str, *, prepend: Path | None = None) -> str:
    """Drop garbage PATH entries and ensure standard bins remain discoverable.

    Cursor/agent shells sometimes inject error text (e.g. ``Unknown command: "bin"``)
    into PATH, which breaks Codex agent shells that inherit Jupyter's env.
    """
    essentials = ("/usr/local/bin", "/usr/bin", "/bin")
    seen: set[str] = set()
    parts: list[str] = []

    def _add(entry: str) -> None:
        if not entry or entry in seen:
            return
        # Reject error text and other non-directory junk.
        if "Unknown command" in entry or "\n" in entry or "\r" in entry:
            return
        if not entry.startswith("/") and not entry.startswith("."):
            return
        seen.add(entry)
        parts.append(entry)

    if prepend is not None:
        _add(str(prepend))
    for entry in path_value.split(os.pathsep):
        _add(entry.strip())
    for entry in essentials:
        if os.path.isdir(entry):
            _add(entry)
    return os.pathsep.join(parts)



def _is_port_free(host: str, port: int) -> bool:
    checked_any_address = False
    try:
        addr_infos = socket.getaddrinfo(
            host or None,
            port,
            type=socket.SOCK_STREAM,
            flags=socket.AI_PASSIVE,
        )
    except OSError:
        return False
    for family, socktype, proto, _canonname, sockaddr in set(addr_infos):
        try:
            sock = socket.socket(family, socktype, proto)
        except OSError:
            continue
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
            if family == socket.AF_INET6 and hasattr(socket, "IPPROTO_IPV6"):
                sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, True)
            sock.bind(sockaddr)
            checked_any_address = True
        except OSError as exc:
            if exc.errno == errno.EADDRNOTAVAIL:
                continue
            return False
        finally:
            sock.close()
    return checked_any_address


def _choose_mcp_port(host: str = "localhost", preferred: int = DEFAULT_MCP_PORT) -> int:
    for port in range(preferred, preferred + 100):
        if _is_port_free(host, port):
            return port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _sync_workspace_user_docs(repo: Path) -> None:
    """Mirror docs/user into workspace/docs for local Jupyter parity with production."""
    src = repo / "docs" / "user"
    dest = repo / "workspace" / "docs"
    if not src.is_dir():
        return
    if dest.is_symlink():
        dest.unlink()
    elif dest.is_dir():
        shutil.rmtree(dest)
    try:
        dest.symlink_to(src.resolve(), target_is_directory=True)
    except OSError:
        shutil.copytree(src, dest)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Start local JupyterLab for mip-jupyter.")
    parser.add_argument("--notebook", default=os.getenv("MIP_NOTEBOOK", DEFAULT_NOTEBOOK))
    parser.add_argument("--host", default=os.getenv("JUPYTER_HOST", DEFAULT_HOST))
    parser.add_argument("--port", type=int, default=int(os.getenv("JUPYTER_PORT", str(DEFAULT_PORT))))
    parser.add_argument(
        "--mcp-port",
        type=int,
        default=int(os.getenv("JUPYTER_MCP_PORT")) if os.getenv("JUPYTER_MCP_PORT") else None,
        help="MCP port for Jupyter tools. Defaults to the first free local port at or above 3001.",
    )
    parser.add_argument("--token", default=os.getenv("JUPYTER_TOKEN", DEFAULT_TOKEN))
    parser.add_argument(
        "--codex-base-url",
        default=os.getenv(ENV_CODEX_BASE_URL, DEFAULT_CODEX_BASE_URL),
        help=f"OpenAI-compatible base URL ending in /v1 (overrides {ENV_CODEX_BASE_URL}).",
    )
    parser.add_argument(
        "--codex-model",
        default=os.getenv(ENV_CODEX_MODEL, DEFAULT_CODEX_MODEL),
        help=f"Served model id on that endpoint (overrides {ENV_CODEX_MODEL}).",
    )
    parser.add_argument("--codex-provider", default=os.getenv("CODEX_VLLM_PROVIDER", DEFAULT_CODEX_PROVIDER))
    parser.add_argument(
        "--codex-context-window",
        type=int,
        default=None,
        help=(
            f"Agent context window in tokens. Defaults to ${ENV_CODEX_CONTEXT_WINDOW} "
            f"(else {DEFAULT_CODEX_CONTEXT_WINDOW})."
        ),
    )
    parser.add_argument(
        "--codex-auto-compact-limit",
        type=int,
        default=None,
        help=(
            f"Auto-compaction token limit. Defaults to ${ENV_CODEX_AUTO_COMPACT_LIMIT} "
            f"(else {DEFAULT_CODEX_AUTO_COMPACT_LIMIT})."
        ),
    )
    parser.add_argument(
        "--codex-reasoning-effort",
        default=os.getenv("CODEX_REASONING_EFFORT", DEFAULT_CODEX_REASONING_EFFORT),
        choices=("minimal", "low", "medium"),
    )
    parser.add_argument(
        "--enable-native-jupyter-mcp",
        action="store_true",
        default=_env_flag("CODEX_ENABLE_NATIVE_JUPYTER_MCP"),
        help="Forward Jupyter MCP as native Responses MCP tools. Do not use with the vLLM shell bridge.",
    )
    return parser


def _codex_settings_from_args(args: argparse.Namespace) -> CodexSettings:
    return CodexSettings.resolve(
        base_url=args.codex_base_url,
        model=args.codex_model,
        provider=args.codex_provider,
        context_window=args.codex_context_window,
        auto_compact_limit=args.codex_auto_compact_limit,
        reasoning_effort=args.codex_reasoning_effort,
        mcp_port=args.mcp_port,
        enable_native_jupyter_mcp=args.enable_native_jupyter_mcp,
    )


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.mcp_port is None:
        args.mcp_port = _choose_mcp_port()
    root = _repo_root()
    work = root / "workspace"
    notebook = _notebook_under_workspace(args.notebook)
    _sync_workspace_user_docs(root)

    env = os.environ.copy()
    env.setdefault("MIP_JUPYTER_ROOT", str(work))
    if not env.get("MIP_AGENT_DOCS"):
        env["MIP_AGENT_DOCS"] = str(root)
    if not env.get("PLATFORM_BACKEND_URL") and not env.get("MIP_BASE_URL"):
        env["PLATFORM_BACKEND_URL"] = DEFAULT_BACKEND_URL
    url = f"http://{args.host}:{args.port}/lab/tree/{notebook}?token={args.token}"

    settings = _codex_settings_from_args(args)

    with tempfile.TemporaryDirectory(prefix="mip-codex-home-") as codex_home:
        codex_home_path = Path(codex_home)
        jupyter_config_path = codex_home_path / "jupyter_ai_config.json"
        wrapper_bin = bootstrap_codex(codex_home_path, jupyter_config_path, settings)

        env["CODEX_HOME"] = codex_home
        env["PATH"] = _sanitize_path(env.get("PATH", ""), prepend=wrapper_bin)
        env["JUPYTER_MCP_URL"] = f"http://127.0.0.1:{args.mcp_port}/mcp"
        # Agent shells may run as root; keep Jupyter runtime under a writable temp dir.
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            runtime_dir = Path("/tmp/mip-jupyter-runtime")
            data_dir = Path("/tmp/mip-jupyter-data")
            runtime_dir.mkdir(parents=True, exist_ok=True)
            data_dir.mkdir(parents=True, exist_ok=True)
            env.setdefault("JUPYTER_RUNTIME_DIR", str(runtime_dir))
            env.setdefault("JUPYTER_DATA_DIR", str(data_dir))

        command = [
            sys.executable,
            "-m",
            "jupyterlab",
            "--no-browser",
            f"--ServerApp.ip={args.host}",
            f"--ServerApp.port={args.port}",
            f"--ServerApp.token={args.token}",
            f"--ServerApp.root_dir={work}",
            f"--ServerApp.default_url=/lab/tree/{notebook}",
            "--config",
            str(jupyter_config_path),
        ]
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            command.append("--allow-root")

        print(f"JupyterLab URL: {url}")
        print("MIP platform connection: configured")
        print(f"Jupyter AI persona: {MIP_PERSONA_NAME}")
        print(f"CODEX_HOME={codex_home}")
        print(f"Codex model: {settings.model}")
        print(f"Codex reasoning effort: {settings.reasoning_effort}")
        print(f"Codex catalog models: {', '.join(settings.catalog_models)}")
        print(f"Codex provider: {settings.provider}")
        print(f"Codex base_url: {settings.base_url}")
        mcp_forwarding = "native" if settings.enable_native_jupyter_mcp else "shell bridge"
        print(f"Codex model catalog: {codex_home_path / 'model-catalog.json'}")
        if wrapper_bin is not None:
            print(f"Codex ACP wrapper: {wrapper_bin / 'codex-acp'}")
        print(f"Jupyter MCP forwarding: {mcp_forwarding}")
        print(f"Jupyter MCP port: {args.mcp_port}")
        print(f"Jupyter MCP URL: {env['JUPYTER_MCP_URL']}")
        # argv list from local CLI args, no shell.
        return subprocess.call(command, cwd=root, env=env)  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit


if __name__ == "__main__":
    raise SystemExit(main())
