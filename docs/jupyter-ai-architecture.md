# MIP Platform Architecture

How Jupyter AI (Cohort Scout), the MIP platform stack, federated Exaflow workers, and LLM inference fit together.


## Overview

```mermaid
flowchart LR
    subgraph JL["JupyterLab container"]
        Chat["Jupyter AI Chat"]
        MCP["Jupyter MCP Server<br/>(curated tools)"]
        Codex["codex-acp"]
        CLI["jupyter_mcp_cli<br/>(shell bridge)"]

        Chat -->|"ACP"| Codex
        Codex -->|"shell commands"| CLI
        CLI -->|"HTTP POST<br/>JUPYTER_MCP_URL"| MCP
    end

    Backend["platform-backend<br/>/services"]
    Controller["exaflow-controller"]
    CSCSW["exaflow-workers<br/><i>CSCS Alps, Lugano</i>"]
    HW["exaflow-workers<br/><i>Hospital remote VMs</i>"]

    subgraph LLM["LLM inference"]
        VLLM["SGLang<br/>/v1/responses<br/>RadixArk/Qwen3.8-Flash-Next-NVFP4"]
    end

    MCP -->|"mip.Client.from_env()<br/>metadata & analysis"| Backend
    Backend --> Controller
    Controller -->|"orchestrates"| CSCSW
    Controller -->|"orchestrates"| HW
    Codex -->|"HTTP Responses API"| VLLM

    style JL fill:#f9f9f9,stroke:#666
    style LLM fill:#eef6ff,stroke:#4a7fc1
    style CSCSW fill:#fff8f0,stroke:#c48a4a
    style HW fill:#fff8f0,stroke:#c48a4a
```

## Federated execution stack

| Component | Role |
|-----------|------|
| **Jupyter MCP Server** | Curated tools inside JupyterLab; MIP calls go to platform-backend via `mip.Client.from_env()`. Notebook edit/run tools stay local. |
| **platform-backend** | Spring Boot API under `/services`; entry point for notebooks and portal — never Exaflow directly. |
| **exaflow-controller** | Quart HTTP API; validates analysis requests, selects execution strategy, orchestrates worker tasks. |
| **exaflow-workers (CSCS)** | gRPC workers running inside **CSCS Alps** (Lugano), the Swiss National Supercomputing Centre. |
| **exaflow-workers (hospitals)** | gRPC workers on **remote VMs at hospital sites**, holding local clinical data. |
| **LLM inference** | OpenAI-compatible `/v1/responses` served by SGLang (`RadixArk/Qwen3.8-Flash-Next-NVFP4`) for Cohort Scout via `CODEX_VLLM_BASE_URL`. |

Flow: `Jupyter MCP Server → platform-backend → exaflow-controller → exaflow-workers` (at CSCS or hospital remote VMs).

## Jupyter AI paths

| Path | When it runs | Notes |
|------|--------------|-------|
| Chat → Codex → inference endpoint | Every user message | Cohort Scout calls the endpoint `/v1/responses` for inference. |
| Codex → shell bridge → MCP | Tool use from Codex | The Responses endpoint rejects native `mcp` tools; Codex uses `jupyter_mcp_cli` instead. |
| MCP → platform-backend → Exaflow | MIP metadata and analysis | MCP tools call `/services`; backend forwards execution to the controller and workers. |
| MCP → local workspace | Notebook edits and runs | Outline, edit, and run-cell tools stay inside the JupyterLab container. |

## Why the shell bridge

The Responses endpoint rejects native `mcp` and `web_search_preview` tool payloads. The runner sets `JUPYTER_MCP_URL` and instructs Codex to call curated tools through the CLI bridge. Native MCP forwarding is opt-in via `CODEX_ENABLE_NATIVE_JUPYTER_MCP=1`.

## LLM inference

LLM inference uses a configured OpenAI-compatible endpoint
(`CODEX_VLLM_BASE_URL`, SGLang served id `RadixArk/Qwen3.8-Flash-Next-NVFP4`).
Hub passes `CODEX_REASONING_EFFORT` (default `low`). Catalog `base_instructions`
steer one topic-scoped `read-guide` cold start. This is separate from federated
analysis compute at CSCS and hospital workers.

Serve with `--tool-call-parser qwen3_coder` and `--reasoning-parser qwen3`, and
thinking disabled by default for interactive chat. See
[operators.md](operators.md) for the profile and
[jupyter-ai-codex.md](jupyter-ai-codex.md) for verification.
