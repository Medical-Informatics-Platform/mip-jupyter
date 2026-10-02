#!/usr/bin/env bash
# Operator acceptance gate for Cohort Scout shell guard + vLLM (no Jupyter UI required).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BASE_URL="${CODEX_VLLM_BASE_URL:?set it to the OpenAI-compatible base URL ending in /v1}"
MODEL="${CODEX_VLLM_MODEL:-RadixArk/Qwen3.8-Flash-Next-NVFP4}"
BASE_URL="${BASE_URL%/}"   # paths are appended below

echo "Checking vLLM models at ${BASE_URL}..."
curl -fsS "${BASE_URL}/models" | grep -q "${MODEL}"

echo "Checking Responses API..."
# The served model may emit a reasoning block before the final message; keep headroom.
curl -fsS "${BASE_URL}/responses" \
  -H 'Content-Type: application/json' \
  -d "{\"model\":\"${MODEL}\",\"input\":\"Reply with OK only.\",\"max_output_tokens\":2048}" \
  | grep -q '"status"'

echo "Running shell guard, persona, and context-eval regression tests..."
cd "${ROOT}"
uv run pytest \
  dev/test_shell_guard.py \
  dev/test_codex_bootstrap.py \
  dev/test_cohort_scout_eval.py \
  dev/test_stroke_federated.py \
  -q \
  -k "shell or tool_call_parse or vllm_unavailable or select_primary or coverage or format_logistic or parse_logistic or eval or base_instructions or offline_eval or catalog_defaults or from_env_default"

echo "Running offline context budget eval..."
uv run python -m dev.cohort_scout_eval

echo "Acceptance gate passed."
echo "Manual UI check (optional): in JupyterLab chat, send:"
echo "  @Cohort Scout run a novel statistical stroke analysis with significance on SSR"
echo "Optional live TTFT: scripts/eval-cohort-scout-context.sh --live-vllm"
