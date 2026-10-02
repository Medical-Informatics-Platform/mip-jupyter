# MIP Jupyter LLM Wiki — Index

**Read when:** Intent is unclear and you need to pick a task page.

**Skip if:** Production Cohort Scout catalog instructions already name the page,
or the user needs a one-line answer already in the active notebook.

## Production cold start (Cohort Scout)

Do **not** load this index, `AGENTS.md`, or `00-agent-workspace` by default.
Call one `jupyter-mcp read-guide --page PAGE` (add `--topic` when intent is known).
Use this index only when the page is unclear. Use `00` only for refusal/scope wording.
Never bare `read-guide` and never `find`/`grep` the wiki tree.

## IDE / Cursor startup

1. `AGENTS.md` is the bootstrap — do not reread it.
2. Pick **one** page from the routing table (or go straight to it).
3. Open source/notebooks only when that page points there.
4. After compaction/handoff: `06-runtime-state.md` + minimal `.llm/` for the chat.
5. No full-repo `find` / `grep` / tree listing on startup.

## Ignore unless a page requires it

`.venv/`, `.ipynb_checkpoints/`, `.playwright-cli/`, `uv.lock`, `build/`,
`*.egg-info/`, `__pycache__/`, and `python-client/tests/` (except client work).

## Docs layers

- **Agent wiki** (`docs/llm/`) — one page at a time via `read-guide`
- **User docs** — workspace `docs/` via `search-docs`
- **Production:** shell bridge only; never scan the bundled wiki tree

## Routing

| User intent | Wiki page | Suggested `--topic` |
|-------------|-----------|---------------------|
| Refusal / product language | `00-agent-workspace` | `scope` |
| New MIP user | `01-onboarding` | — |
| Analysis pipeline | `02-analysis-workflow` | — |
| Algorithm catalog | `07-pipeline-algorithms` | `methods` |
| MIP Python API | `03-mip-client-api` | — |
| Notebook create/edit | `04-jupyter-mcp` | `payload` |
| Env / `Client.from_env()` | `05-env-and-backend` | `from_env` |
| Compaction / handoff | `06-runtime-state` | — |
| Exploration | `agent-exploration` | — |
| Stroke / novel stroke | `recipes/stroke-analysis` only | `novel` |
| Client / tests / commits | `dev-contributor` | — |

Full API contract: [expected_library.md](../../expected_library.md) — not on startup.

## Wiki page rules

One page = one job; ≤~80 lines. Prefer `--topic` over full-page reads.

**Next file:** the single routed wiki page for the user's task.
