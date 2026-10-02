# Jupyter MCP — Curated Notebook and MIP Tools

**Read when:** Create, edit, run, or inspect notebooks from Jupyter AI / Codex.

**Skip if:** API-only questions (`03-mip-client-api.md`). Off-topic → `00-agent-workspace.md`.

## Shell bridge

vLLM rejects native Responses `mcp` tools. Use:

```bash
python -m mip_jupyter_dev.jupyter_mcp_cli <command> ...
# or: jupyter-mcp <command> ...
```

`JUPYTER_MCP_URL` is set by the notebook runner.

## Tool payload safety

Keep args **small valid JSON**. Prefer a few small related calls over one giant
payload; split large edits.

**Forbidden:** `write_stdin` / heredocs / shell redirects into workspace;
giant `python -c`; `--content-file -`; paths outside the workspace; `cat` on
`.ipynb` JSON; replaying huge scripts after compaction.

**Safe (preferred):** write the full analysis as **ONE** `scratch/<name>.py` with
`# %%` cell markers via `scratch-write-file`, run `python scratch/<name>.py` to
validate (exit 0), then `scratch-to-notebook` **once** → `open-file` /
`notebook-outline`. Do **not** build cell-by-cell fragments.

On **tool-call formatting errors**: new chat, `scratch-list`, resume existing
`scratch/*.py` with smaller steps.

## Build the notebook (single-shot)

| Choose | When |
|--------|------|
| **Write ONE script → transfer once (default)** | Write the whole analysis as ONE `scratch/<name>.py` with `# %%` markers via `scratch-write-file`; validate with `python scratch/<name>.py` (exit 0); then `scratch-to-notebook` once. Never write per-cell fragment files. |
| **Direct cell tools** | Only for a tiny tweak to an existing notebook (one `append-code`/`edit-cell`/`run-cell`). |

## Verify before transfer

After writing the ONE `scratch/<name>.py` with `# %%` markers, run it from the
workspace root before `scratch-to-notebook`:

```bash
python scratch/<name>.py
```

Exit 0 before `scratch-to-notebook`. `# %%` markers split into multiple cells;
unmarked scripts transfer as one code cell. Prefer `python scratch/<name>.py`
over `python -c` / heredocs.

## Common commands

```bash
# context — always prefer --topic when intent is known
jupyter-mcp read-guide --page 04-jupyter-mcp --topic payload
jupyter-mcp read-guide --page recipes/stroke-analysis --topic novel
jupyter-mcp search-docs "Client.from_env"
jupyter-mcp notebook-outline PATH
jupyter-mcp read-cell PATH INDEX --max-chars 3000

# scratch (ONE script, one transfer; each inline arg is one line)
jupyter-mcp scratch-list
jupyter-mcp scratch-write-file scratch/my.py "# %% setup" "import mip"
jupyter-mcp scratch-write-file scratch/my.py --content-file draft.py
jupyter-mcp scratch-copy-template scratch/my.py --source examples/algorithm_examples.py  # template start
jupyter-mcp scratch-append-lines scratch/my.py "# comment"
jupyter-mcp scratch-replace-snippet scratch/my.py "OLD" "NEW"
jupyter-mcp scratch-to-notebook scratch/my.py scratch/my.ipynb --title "My analysis"

# notebook
jupyter-mcp create-notebook scratch/x.ipynb
jupyter-mcp append-markdown|append-code|edit-cell|open-file ...
jupyter-mcp run-cell PATH INDEX --timeout 30   # also runs prior code cells
jupyter-mcp run-all-cells PATH --timeout 60

# MIP metadata (defaults are intentionally small)
jupyter-mcp mip-env-status
jupyter-mcp mip-catalog-summary --limit 10
jupyter-mcp mip-data-model-summary stroke --version 3.7
jupyter-mcp mip-search-variables stroke "NIHSS" --version 3.7 --limit 10
jupyter-mcp mip-algorithm-summary --limit 20
```

Multi-step exploration: `read-guide --page agent-exploration`.

## Workflow

1. `read-guide --page … --topic …` only when needed (skip INDEX/`00` by default)
2. Outline before `read-cell`
3. Write ONE `scratch/<name>.py` with `# %%` markers via `scratch-write-file` → `python scratch/<name>.py` (exit 0) → `scratch-to-notebook` once; direct cell tools only for a tiny tweak to an existing notebook
4. New notebooks under `scratch/` unless named otherwise
5. Edit by index; re-read before replying; summarize run outputs

**Next file:** the notebook you are editing, if any.
