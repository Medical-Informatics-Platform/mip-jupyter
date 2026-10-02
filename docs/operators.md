# Operators

Deployment and runtime orchestration for MIP Jupyter live in the **`mip/deployment`** repository, not in mip-jupyter.

## What mip-jupyter provides

| Deliverable | Location |
|-------------|----------|
| Single-user Jupyter image | `docker/singleuser/Dockerfile` |
| JupyterHub image and config | `docker/hub/` |
| `mip` Python client | `python-client/` (installed in images) |
| User workspace template | `workspace/` + `docs/user/` → `/home/jovyan/work` |
| Agent wiki (not user-visible) | `docs/llm/` + `AGENTS.md` → `/opt/mip-agent-docs/` |

## Environment contract

Notebooks and the `mip` client expect:

- `PLATFORM_BACKEND_URL` or `MIP_BASE_URL` — backend URL ending in `/services`
- `MIP_TOKEN` or `PLATFORM_TOKEN` — bearer token for platform-backend
- Optional: `JUPYTERHUB_API_URL`, `JUPYTERHUB_API_TOKEN` for hub-side token refresh

When Cohort Scout is enabled, Hub spawners also pass. Everything is runtime
configuration: moving the agent to another host, port, or model id needs no code
change and no image rebuild.

- `CODEX_VLLM_BASE_URL` (required to bootstrap Codex; base URL ending in `/v1`,
  trailing slash trimmed)
- `CODEX_VLLM_MODEL` (default `RadixArk/Qwen3.8-Flash-Next-NVFP4`; any served id is accepted)
- `CODEX_REASONING_EFFORT` (default `low`; use `medium` for exploration pods)
- Optional: `CODEX_VLLM_PROVIDER`, `CODEX_MODEL_CONTEXT_WINDOW`,
  `CODEX_AUTO_COMPACT_TOKEN_LIMIT`

Any served id is accepted, so pointing the agent at a different model needs no
code change. Set the two budget variables when the served model's context differs
from the defaults; omit them otherwise.

Hub spawner configuration should inject backend URL and token at spawn time. See `docker/hub/jupyterhub_config.py` for the reference implementation.

Keep the Codex agent window at **131072** (default) even when the inference
server allows `context_length=262144`. Do not enable native Responses MCP for
this stack; Cohort Scout uses the shell bridge.

### Required serve profile (`RadixArk/Qwen3.8-Flash-Next-NVFP4`)

Serve `RadixArk/Qwen3.8-Flash-Next-NVFP4` on an OpenAI-compatible
`/v1/responses` endpoint. The deployed instance is SGLang and keeps the
checkpoint id as the served id (no `--served-model-name` alias); the Codex
provider id stays `vllm` because it only selects `wire_api = "responses"`.
Serve settings read back from `/server_info`:

- `--tool-call-parser qwen3_coder` with automatic tool choice
- `--reasoning-parser qwen3`
- `--context-length 262144` (agent context stays capped at 131072 in Codex)
- `--mem-fraction-static 0.95` and `--max-running-requests 8` (KV cache
  headroom with light concurrency)
- `trust_remote_code` enabled, as required by the checkpoint

The served id must equal `CODEX_VLLM_MODEL` exactly, including the `RadixArk/`
prefix: Codex sends that value as the request `model`. Keep `--served-model-name`
unset, or set `CODEX_VLLM_MODEL` to whatever alias the server does expose.

The endpoint takes no API key and the deployed instance binds `0.0.0.0:8888`, so
keep it on a trusted network and treat it as non-production inference.

Reasoning is on by default, which burns output budget on CoT before the final
message. Codex cannot pass `chat_template_kwargs` on the Responses path, so
disable thinking at serve time for default chat if interactive latency matters;
use `CODEX_REASONING_EFFORT=medium` only on exploration pods if you re-enable
thinking server-side for those workloads.

## Image build and release

```bash
docker build -f docker/singleuser/Dockerfile -t mip-jupyter:<tag> .
docker build -f docker/hub/Dockerfile -t mip-jupyterhub:<tag> .
```

Full checklist: [`release-process.md`](release-process.md).

## Where to configure production

- **Compose / Kubernetes / Helm** — `mip/deployment`
- **Image tags in Hub** — update `JUPYTER_SINGLEUSER_IMAGE` in deployment values or `docker/hub/jupyterhub_config.py`
- **Keycloak / auth** — `mip/deployment` (Hub refuses to start without `KEYCLOAK_CLIENT_ID`; `JUPYTERHUB_USE_DUMMY_AUTH=1` enables dummy auth for local testing only)
- **Platform token refresh** — Hub `platform_token_service.py`; validate in deployment integration tests

## Smoke test after rollout

1. User logs in via Hub and lands on `Welcome.ipynb`.
2. `import mip` and `mip.Client.from_env()` succeed.
3. File browser shows `Welcome.ipynb`, `examples/`, `docs/`, `scratch/` only.
4. `docs/llm/` and `python-client/` are **not** visible to users.
5. Jupyter AI agents can call `agent_read_guide` (reads `/opt/mip-agent-docs/`).
