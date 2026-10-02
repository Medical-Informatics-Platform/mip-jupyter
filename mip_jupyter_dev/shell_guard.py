"""Shell command guard for Codex exec_command in mip-jupyter."""

from __future__ import annotations

import argparse
import re
import sys

MAX_SHELL_COMMAND_CHARS = 2048

_HEREDOC_PATTERN = re.compile(r"<<\s*['\"]?[A-Za-z0-9_]+['\"]?", re.MULTILINE)
_NOTEBOOK_READ_PATTERN = re.compile(
    r"\b(cat|head|tail|less|more|sed|awk|python\s+-c)\b[^\n]*\.ipynb\b",
    re.IGNORECASE,
)
_SHELL_REDIRECT_PATTERN = re.compile(
    r">\s*(scratch/|workspace/|/home/jovyan/work/)",
    re.IGNORECASE,
)
_OVERSIZED_PYTHON_C_PATTERN = re.compile(
    r"python(?:3)?\s+-c\s+['\"].{500,}['\"]",
    re.DOTALL | re.IGNORECASE,
)


def validate_shell_command(command: str) -> str | None:
    """
    Return an error message when *command* violates bounded shell policy.

    Return None when the command is allowed.
    """
    text = str(command or "").strip()
    if not text:
        return "Empty shell command is not allowed."
    if len(text) > MAX_SHELL_COMMAND_CHARS:
        return (
            f"Shell command exceeds {MAX_SHELL_COMMAND_CHARS} characters; "
            "use jupyter-mcp scratch-* tools or smaller steps."
        )
    lowered = text.lower()
    if "write_stdin" in lowered:
        return "write_stdin is disabled; use scratch-append-lines or append-code."
    if _HEREDOC_PATTERN.search(text):
        return "Heredocs are disabled; use scratch-write-file or append-code."
    if _NOTEBOOK_READ_PATTERN.search(text):
        return "Raw notebook file reads are disabled; use notebook-outline or read-cell."
    if _SHELL_REDIRECT_PATTERN.search(text):
        return "Shell file writes are disabled; use scratch-write-file or append-code."
    if _OVERSIZED_PYTHON_C_PATTERN.search(text):
        return "Oversized python -c payloads are disabled; use scratch/*.py scripts."
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Codex shell commands.")
    parser.add_argument("--validate", required=True, help="Shell command string to validate.")
    args = parser.parse_args(argv)
    error = validate_shell_command(args.validate)
    if error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
