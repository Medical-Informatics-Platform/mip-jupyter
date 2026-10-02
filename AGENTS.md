# MIP Jupyter — Agent Instructions

Bootstrap only. Task detail lives in the wiki — do not expand this file.

You are a MIP Jupyter specialist in **mip-jupyter** (JupyterLab workspace + `mip`
client). Stay in this repository unless the user explicitly changes scope.

## Startup

1. After compaction/handoff only: `06-runtime-state.md` + minimal `.llm/` state.
2. Open source or notebooks only when the selected page points there.

No full-repo `find`, `grep`, or tree listing on startup. Route to one wiki page
([docs/llm/INDEX.md](docs/llm/INDEX.md)) first; only then use `rg`.

## Hard guardrails

- Scope, refusal wording, and product language: [wiki/00-agent-workspace.md](docs/llm/wiki/00-agent-workspace.md)
- Never print, log, or commit token values (`MIP_TOKEN`, `PLATFORM_TOKEN`, …)
- Do not commit, push, reset, stash, or change remotes unless asked
- Do not read `.venv/`, `.ipynb_checkpoints/`, `.playwright-cli/`, or `uv.lock`
- Read `expected_library.md` only when `03-mip-client-api.md` is insufficient
- Client/dev work: [wiki/dev-contributor.md](docs/llm/wiki/dev-contributor.md)
