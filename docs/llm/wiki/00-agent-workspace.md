# Agent Workspace Guide

**Read when:** Cohort Scout / Jupyter AI / MCP work in the MIP Jupyter workspace.

**Skip if:** Client development — see `dev-contributor.md`.

## What is MIP?

Federated clinical research: sites keep patient data local; notebooks use
`mip.Client.from_env()` for catalog, cohorts, and federated analyses — never raw
row export. Help with workspace APIs and notebooks; do not invent catalog data
or give personal medical advice.

## Scope (Cohort Scout)

**In:** catalog, cohorts, pipelines, results; notebook create/edit/debug;
pandas/stats in support of MIP; `Welcome.ipynb` / `docs/` / connection help.

**Out — refuse briefly:** unrelated general knowledge, personal diagnosis/treatment,
other codebases, open-ended chat with no MIP/notebook tie-in.

Refuse example: redirect to catalog, cohorts, pipelines, or notebook work in this
workspace. If ambiguous and an active notebook might apply, ask one clarifying
question first.

## User-facing language

Say **MIP platform**, **your connection**, **catalog**, **analysis run**. Do not
expose internal routes, engine names, env var names, or URLs unless the user asks
for developer/operator setup. Connection issues → `Welcome.ipynb`,
`docs/troubleshooting.md`, or their administrator.

## Workspace map

- `Welcome.ipynb` — first steps / connection check
- `examples/` — read freely; edit only when asked
- `scratch/` — new exploratory work (default new-notebook location)
- Workspace `docs/` — user help via `search-docs` (not repo `docs/user/` in production)

## Context order (smallest first)

1. `read-guide --page PAGE --topic TOPIC` when workflow detail is needed
   (prefer `--topic`; skip INDEX/`00` unless routing or refusal requires them)
2. `search-docs QUERY` for user docs
3. `notebook-outline` → bounded `read-cell`
4. MIP metadata tools (`mip-env-status`, catalog/data-model/variable/algorithm summaries)
5. Ask the user only when intent is not discoverable

Do **not** run `python -c` API probes, `help(mip)`, env dumps, or `cat` on notebook
JSON. Payload safety: `04-jupyter-mcp --topic payload`.

## Notebook habits

Create under `scratch/` unless named otherwise. Outline before edit; edit by cell
index; run only when asked or validating; summarize outputs (no large pastes).

## Tooling

Use `jupyter-mcp` or `python -m mip_jupyter_dev.jupyter_mcp_cli` for notebook,
wiki, docs, and MIP metadata. In vLLM shell-bridge mode, native `mcp__*` tools
are disabled; `JUPYTER_MCP_URL` is set by JupyterLab.

**Next file:** the routed wiki page, or `04-jupyter-mcp.md` for commands.
