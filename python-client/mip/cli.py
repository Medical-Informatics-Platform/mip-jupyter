"""`mip` command line: the bundled agent guide and compact catalog summaries, as JSON."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from . import agent

AGENTS_TEMPLATE = agent.DOCS_ROOT / "AGENTS.laptop.md"
CLAUDE_MD = "@AGENTS.md\n"


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
    return {"ok": True, "written": [str(path) for path in targets]}


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
