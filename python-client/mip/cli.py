"""`mip` command line: the bundled agent guide and compact catalog summaries, as JSON."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

from . import agent, client, keycloak
from .exceptions import MipError

AGENTS_TEMPLATE = agent.DOCS_ROOT / "AGENTS.laptop.md"
CLAUDE_MD = "@AGENTS.md\n"
DATA_NOTICE = (
    "AI assistants send what they read, analysis results included, to their provider. "
    "Check that your MIP data-use terms allow this before you use one."
)


def _signin(action) -> dict[str, Any]:
    try:
        remote = client.remote_urls()
        if remote is None:
            return {"ok": False, "error": "Set MIP_URL to your MIP portal (for example https://<host>) first."}
        return action(*remote)
    except MipError as exc:
        return {"ok": False, "error": str(exc)}


def login(token: bool = False) -> dict[str, Any]:
    """Sign in to the MIP portal at MIP_URL and save the sign-in on this computer.

    Without `token`, in your browser (it shows a link and a code). With it, by pasting a
    token created on the portal's account page, for machines without a browser.
    """

    if token:
        value = getpass.getpass("Paste the token from the portal's account page (input is hidden): ").strip()
        if not value:
            return {"ok": False, "error": "No token entered."}
        return _signin(lambda mip_url, backend_url: keycloak.save_token(mip_url, backend_url, value))

    def show(text: str) -> None:
        # stdout carries the JSON result only.
        print(text, file=sys.stderr, flush=True)

    return _signin(lambda mip_url, backend_url: keycloak.login(mip_url, backend_url, show=show))


def logout() -> dict[str, Any]:
    """Revoke and forget this computer's sign-in to MIP_URL, and the token in MIP_API_TOKEN."""

    env_token = os.getenv("MIP_API_TOKEN")
    return _signin(lambda mip_url, backend_url: keycloak.logout(mip_url, backend_url, env_token))


def agent_init(directory: str | Path = ".", *, force: bool = False) -> dict[str, Any]:
    """Write AGENTS.md (and a CLAUDE.md that imports it) so AI assistants know how to use MIP here."""

    folder = Path(directory).expanduser()
    targets = [folder / "AGENTS.md", folder / "CLAUDE.md"]
    existing = [str(path) for path in targets if path.exists()]
    if existing and not force:
        return {"ok": False, "error": "Files already exist; use --force to overwrite.", "existing": existing}
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(AGENTS_TEMPLATE, targets[0])
    targets[1].write_text(CLAUDE_MD, encoding="utf-8")
    return {"ok": True, "written": [str(path) for path in targets], "notice": DATA_NOTICE}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mip", description="MIP guide and catalog helpers for AI agents.")
    commands = parser.add_subparsers(dest="command", required=True)

    guide = commands.add_parser("guide", help="List guide pages, read one, or search them")
    guide.add_argument("page", nargs="?")
    guide.add_argument("--topic")
    guide.add_argument("--search")
    guide.add_argument("--max-chars", type=int, default=agent.DEFAULT_WIKI_MAX_CHARS)
    guide.add_argument("--limit", type=int, default=5)

    commands.add_parser("env-status", help="Is the MIP connection configured? (never shows values)")
    login_cmd = commands.add_parser("login", help="Sign in to MIP_URL, once per computer")
    login_cmd.add_argument("--token", action="store_true", help="Paste a token from the portal's account page instead")
    commands.add_parser("logout", help="Revoke and forget this computer's sign-in to MIP_URL")

    catalog = commands.add_parser("catalog", help="Data models you can access")
    catalog.add_argument("--limit", type=int, default=agent.DEFAULT_CATALOG_LIMIT)

    data_model = commands.add_parser("data-model", help="Datasets, groups and variables of one data model")
    data_model.add_argument("label")
    data_model.add_argument("--version")
    data_model.add_argument("--variables", action="store_true")
    data_model.add_argument("--groups", action="store_true")
    data_model.add_argument("--limit", type=int, default=agent.DEFAULT_DATA_MODEL_LIST_LIMIT)

    search = commands.add_parser("search-variables", help="Search variables in one data model")
    search.add_argument("label")
    search.add_argument("query", nargs="+")
    search.add_argument("--version")
    search.add_argument("--limit", type=int, default=agent.DEFAULT_VARIABLE_SEARCH_LIMIT)

    algorithms = commands.add_parser("algorithms", help="Available algorithms")
    algorithms.add_argument("--limit", type=int, default=agent.DEFAULT_ALGORITHM_SUMMARY_LIMIT)

    agent_cmd = commands.add_parser("agent", help="Set up a folder for an AI assistant")
    agent_actions = agent_cmd.add_subparsers(dest="action", required=True)
    init = agent_actions.add_parser("init", help="Write AGENTS.md and CLAUDE.md into a folder")
    init.add_argument("directory", nargs="?", default=".")
    init.add_argument("--force", action="store_true")
    return parser


def run(args: argparse.Namespace) -> dict[str, Any]:
    command = args.command
    if command == "guide":
        if args.search:
            return agent.search_guide(args.search, args.limit)
        if args.page is None and args.topic is None:
            return agent.list_guide_pages()
        return agent.read_guide(args.page, args.topic, args.max_chars)
    if command == "env-status":
        return agent.env_status()
    if command == "login":
        return login(token=args.token)
    if command == "logout":
        return logout()
    if command == "catalog":
        return agent.catalog_summary(args.limit)
    if command == "data-model":
        return agent.data_model_summary(args.label, args.version, args.variables, args.groups, args.limit)
    if command == "search-variables":
        return agent.search_variables(args.label, " ".join(args.query), args.version, args.limit)
    if command == "algorithms":
        return agent.algorithm_summary(args.limit)
    if command == "agent":
        return agent_init(args.directory, force=args.force)
    raise AssertionError(command)


def main(argv: list[str] | None = None) -> int:
    try:
        result = run(_parser().parse_args(argv))
    except ValueError as exc:
        result = {"ok": False, "error": str(exc)}
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
