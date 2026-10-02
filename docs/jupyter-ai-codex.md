# Jupyter AI Codex Prototype

This prototype adds Jupyter AI to the local JupyterLab workflow so developers can test a Codex assistant backed by a self-hosted `/v1/responses` endpoint. The repository does not include personal credentials or tokens.

Jupyter AI v3 discovers ACP-compatible agents from the runtime environment. The local runner starts JupyterLab with a temporary Codex configuration that points Cohort Scout at a Responses-compatible `/v1/responses` endpoint (SGLang today) and the `RadixArk/Qwen3.8-Flash-Next-NVFP4` model.

Architecture overview and Mermaid source: [jupyter-ai-architecture.md](jupyter-ai-architecture.md).

References:

- Codex CLI: https://developers.openai.com/codex/cli
- Codex CLI README: https://github.com/openai/codex

## Run JupyterLab

From the repository root:

```bash
uv sync
uv run mip-notebook
```

Open:

```text
http://127.0.0.1:8888/lab/tree/examples/feres_analysis.ipynb?token=dev
```

## Install Codex ACP

Optionally install the Codex CLI for local debugging (the image ships only codex-acp):

```bash
npm install -g @openai/codex
codex --version
```

Install the Codex ACP adapter required by Jupyter AI:

```bash
npm install -g @zed-industries/codex-acp
```

The Codex workflow uses a temporary `CODEX_HOME` containing `config.toml` and `model-catalog.json`:

```toml
model = "RadixArk/Qwen3.8-Flash-Next-NVFP4"
model_provider = "vllm"
model_catalog_json = "/tmp/mip-codex-home-.../model-catalog.json"
model_context_window = 131072
model_auto_compact_token_limit = 40000
model_reasoning_effort = "low"
model_reasoning_summary = "none"
model_supports_reasoning_summaries = false
approval_policy = "never"
sandbox_mode = "danger-full-access"
model_verbosity = "low"
web_search = "disabled"

[features]
multi_agent = false

[model_providers.vllm]
name = "vLLM"
base_url = "<CODEX_VLLM_BASE_URL>"
wire_api = "responses"
```

The generated model catalog contains only
`RadixArk/Qwen3.8-Flash-Next-NVFP4` (the SGLang served id) with a 131072-token agent
context window (served `context_length` is 262144). Default reasoning effort is
`low` for chat speed; set `CODEX_REASONING_EFFORT=medium` for multi-step
exploration. Catalog metadata keeps the Responses payload compatible with the
endpoint by setting `support_verbosity` to `false`, `apply_patch_tool_type` to
`null`, and `supports_parallel_tool_calls` to `false`. On the Responses path,
`use_responses_lite` is `false` so shell/function tool calls are returned (lite
mode caused plain-text echoes instead of tool execution).

The runner also prepends a generated `codex-acp` wrapper to `PATH`. The wrapper passes `-c approval_policy="never"`, `-c sandbox_mode="danger-full-access"`, and `-c shell_environment_policy.inherit="all"` directly to `codex-acp`; this is needed because the ACP process otherwise starts Codex with `on-request` approvals and a read-only sandbox even when the temporary `config.toml` contains the desired values.

If the vLLM endpoint is unavailable during a chat request, Cohort Scout catches the likely ACP/Codex connection error and replies with a short service-unavailable message instead of exposing a raw traceback to the user.

The runner starts a curated Jupyter MCP wrapper server by default. Shell-bridge
mode does not emit `builtin_mcp_servers` or a Codex `[mcp_servers]` section, so it
does not forward that server as native Responses `mcp` tools to vLLM. The
current vLLM Responses shim rejects native `mcp` and `web_search_preview` tool
payloads with `Object of type Undefined is not JSON serializable`.

Instead, Codex receives `JUPYTER_MCP_URL` and model instructions to call the MCP server through the shell bridge:

```bash
python -m dev.jupyter_mcp_cli create-notebook scratch/mcp_probe.ipynb
python -m dev.jupyter_mcp_cli append-markdown scratch/mcp_probe.ipynb "MCP OK"
```

The bridge still calls the Jupyter MCP server; it just avoids sending a native
Responses `mcp` tool type to vLLM. Native MCP forwarding can be enabled with
`CODEX_ENABLE_NATIVE_JUPYTER_MCP=1` only for providers that support Responses
MCP tools. When native forwarding is enabled, the generated Codex config includes
the MCP server and the model instructions allow native MCP calls.

Restart JupyterLab after installing or changing agent binaries so Jupyter AI can rediscover available agents.

### Point the agent at another endpoint or model

Host, port, and model id are runtime configuration; none of the examples below
need a code change or an image rebuild. No endpoint is committed:
`./run-local-llm-codex.sh` requires `CODEX_VLLM_BASE_URL` (export it in your
shell profile), and `uv run mip-notebook` falls back to `http://127.0.0.1:8000/v1`.

```bash
# Remote GPU box through a tunnel (avoid local 8888: JupyterLab owns it)
ssh -L 18000:127.0.0.1:8888 <gpu-host> &
CODEX_VLLM_BASE_URL=http://127.0.0.1:18000/v1 ./run-local-llm-codex.sh

# Different served id (env var, or the flag which wins over it)
CODEX_VLLM_MODEL=org/Other-Model ./run-local-llm-codex.sh
uv run mip-notebook --codex-base-url http://127.0.0.1:8001/v1 --codex-model org/Other-Model

# Budgets for a served id whose context differs from the defaults
CODEX_MODEL_CONTEXT_WINDOW=131072 CODEX_AUTO_COMPACT_TOKEN_LIMIT=40000 \
  ./run-local-llm-codex.sh
```

`python -m dev.codex_bootstrap` (the container and Hub path) reads the
same variables; Hub spawners forward them from the deployment repo. Any served id
is accepted, and one we do not ship defaults to the budgets above.

If the shell bridge regresses, native MCP forwarding should remain disabled for this endpoint. Verify the MCP server directly with:

```bash
python -m dev.jupyter_mcp_cli notebook-outline workspace/examples/feres_analysis.ipynb
```

For parallel local JupyterLab instances, use a different JupyterLab port. The runner chooses a free MCP port automatically unless `JUPYTER_MCP_PORT` or `--mcp-port` is set:

```bash
JUPYTER_PORT=8892 uv run mip-notebook
```

## Check the inference endpoint

From a machine that can reach the inference host:

```bash
curl "${CODEX_VLLM_BASE_URL}/models"
```

Expected model IDs include:

```text
RadixArk/Qwen3.8-Flash-Next-NVFP4
```

The local and Hub runners use `RadixArk/Qwen3.8-Flash-Next-NVFP4`.

The endpoint must support the Responses API path used by Codex:

```bash
curl "${CODEX_VLLM_BASE_URL}/responses" \
  -H 'Content-Type: application/json' \
  -d '{"model":"RadixArk/Qwen3.8-Flash-Next-NVFP4","input":"Say OK only","max_output_tokens":2048}'
```

`RadixArk/Qwen3.8-Flash-Next-NVFP4` emits a reasoning block before the final message by default;
use at least `2048` `max_output_tokens` in manual curl tests. For interactive Cohort Scout
latency, serve with thinking disabled by default (see [operators.md](operators.md)).

## Agent Onboarding

Jupyter AI Codex is steered by a layered wiki instead of ad-hoc repo exploration:

- **Production Codex:** `read-guide` reads the default workspace guide or an allowlisted routed page from `/opt/mip-agent-docs/`; `search-docs` searches user docs in workspace `docs/`.
- [`AGENTS.md`](../AGENTS.md) — repository bootstrap entry point for Cursor and IDE agents
- [`docs/llm/INDEX.md`](../docs/llm/INDEX.md) — wiki map and task routing table
- [`docs/user/`](../docs/user/) — canonical user documentation (shipped to workspace `docs/`)

The notebook runner injects slim `base_instructions` in the generated Codex model
catalog. Production Cohort Scout should cold-start from those instructions plus
**one** `read-guide --page PAGE [--topic …]` — not AGENTS → INDEX → 00. Prefer
`--topic` (`novel`, `payload`, `from_env`, `methods`, `scope`). Hub spawners pass
`CODEX_REASONING_EFFORT` (default `low`) with the vLLM URL/model.

Context budget gate (offline; optional live TTFT):

```bash
scripts/eval-cohort-scout-context.sh
scripts/eval-cohort-scout-context.sh --live-vllm
```

In shell-bridge mode, those instructions require Cohort Scout to use
`jupyter_mcp_cli` for notebook and MIP tool actions; native `mcp__*` tools are
disabled for vLLM. For substantial or multi-step workflows only, the agent
may validate the analysis in a temporary Python file before transferring it to
notebook cells.

The production single-user image seeds `workspace/` and `docs/user/` into `/home/jovyan/work`, bundles agent wiki at `/opt/mip-agent-docs/`, and does not copy client source into the user file browser.

## Verify Jupyter AI and Codex

1. Open JupyterLab.
2. Open the chat panel from the left sidebar, or create a chat from the launcher.
3. Type `@` in the chat input and verify that **Cohort Scout** appears in the persona menu.
   Stock Jupyter AI ACP personas such as Codex, Claude, and Copilot are hidden; Cohort Scout is the only available persona.
4. Use one of the existing notebooks as context, for example `workspace/examples/feres_analysis.ipynb` or `workspace/Welcome.ipynb`.
5. Send one of these prompts:

```text
@Cohort Scout explain the structure of this workspace.
@Cohort Scout inspect workspace/Welcome.ipynb and summarize what a new MIP user should do first.
@Cohort Scout explain how mip.Client.from_env() gets configuration.
@Cohort Scout create a new scratch notebook named mcp_probe.ipynb with one markdown cell that says MCP OK.
```

The current prototype is considered successful if the Jupyter AI chat UI opens, Cohort Scout appears after the runtime agent setup, it can answer against an existing notebook or workspace file, and it can use the Jupyter MCP shell bridge to create or edit a notebook without any credentials committed to the repository.

### Golden prompts (context efficiency)

Use these prompts to verify that Cohort Scout follows the wiki instead of grepping the full repo. Success means a correct answer with **at most three targeted file reads** before replying (no broad `find` or repo-wide `grep` on startup).

| Prompt | Expected reads |
|--------|----------------|
| `@Cohort Scout explain how mip.Client.from_env() gets configuration` | `read-guide --page 05-env-and-backend --topic "Client.from_env"` |
| `@Cohort Scout summarize what a new MIP user should do first` | `read-guide --page 01-onboarding` and optionally `workspace/Welcome.ipynb` outline |
| `@Cohort Scout create a new scratch notebook named mcp_probe.ipynb with one markdown cell that says MCP OK` | MCP CLI only; use `read-guide --page 04-jupyter-mcp` if command details are needed |
| `@Cohort Scout run a novel statistical stroke analysis with significance on SSR` | `read-guide --page recipes/stroke-analysis --topic novel`; `mip-data-model-summary stroke --version 3.7`; confirm SSR coverage; `scratch-write-file scratch/<name>.py` (whole script, `# %%` markers, one arg per line or `--content-file`); `scratch-replace-snippet` for small fixes; run script; `scratch-to-notebook`; no heredocs |

Success for the stroke prompt means: bounded metadata discovery, SSR-only dataset (no SSR+even/odd mix), confirmed SSR coverage, a **new** scratch script derived from `examples/algorithm_examples.py` (trimmed to one hypothesis), federated `describe` / `t_test` / `chi_square_test` / `logistic_regression` (no `Pipeline.run()`), primary adjusted logistic **OR (95% CI)** on the OR scale, a populated `scratch/<name>.ipynb`, aggregate results only, and no giant shell payloads or raw row extraction.

## Image smoke test (operators)

After building the single-user image, run:

```bash
scripts/smoke-singleuser-image.sh hbpmip/mip-jupyter:<tag>
```

The script checks Jupyter status, Codex/jupyter-mcp wrappers, shell-bridge config (no native `[mcp_servers]`), `read-guide --page`, and `notebook-outline`.

For vLLM and parse-error acceptance (no UI):

```bash
scripts/accept-cohort-scout-vllm.sh
```

After deploying a new image tag, recreate existing single-user pods so they pull the updated image; `imagePullPolicy` alone does not refresh already-running pods.

## Production Notes

This prototype is a local development workflow. Do not treat it as a production JupyterHub rollout.

Before enabling AI agents in shared Hub environments, review:

- where temporary Codex runtime state is stored
- whether agents can read other users' files or mounted secrets
- command execution and approval behavior
- network egress and model-provider policy
- audit logging and support expectations
