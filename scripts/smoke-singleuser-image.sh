#!/usr/bin/env bash
# Smoke-test a built mip-jupyter single-user image (shell-bridge / Codex mode).
set -euo pipefail

IMAGE="${1:?Usage: $0 <image:tag>}"
CONTAINER="mip-jupyter-smoke-$$"
TOKEN="${SMOKE_TOKEN:-smoke}"
PORT="${SMOKE_PORT:-8888}"
# The bootstrap only needs a syntactically valid URL; port 9 (discard) keeps the
# smoke test independent of a live inference endpoint.
CODEX_URL="${SMOKE_CODEX_VLLM_BASE_URL:-http://127.0.0.1:9/v1}"
CODEX_MODEL="${CODEX_VLLM_MODEL:-RadixArk/Qwen3.8-Flash-Next-NVFP4}"

cleanup() {
  docker rm -f "${CONTAINER}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker run -d --name "${CONTAINER}" -p "${PORT}:8888" \
  -e JUPYTER_TOKEN="${TOKEN}" \
  -e CODEX_VLLM_BASE_URL="${CODEX_URL}" \
  -e CODEX_VLLM_MODEL="${CODEX_MODEL}" \
  "${IMAGE}"

echo "Waiting for Jupyter..."
curl --retry 60 --retry-delay 2 --retry-all-errors -fsS \
  "http://127.0.0.1:${PORT}/api/status?token=${TOKEN}" >/dev/null

docker exec "${CONTAINER}" sh -lc '
  test -x /tmp/mip-codex-home/bin/jupyter-mcp
  test -x /tmp/mip-codex-home/bin/mip-shell-guard
  test ! -f /tmp/mip-codex-home/bin/codex-acp || test -x /tmp/mip-codex-home/bin/codex-acp
  ! grep -q "\[mcp_servers" /tmp/mip-codex-home/config.toml
  test -d /home/jovyan/work/scratch
  grep -q "# %%" /home/jovyan/work/examples/algorithm_examples.py
'

docker exec "${CONTAINER}" python -m mip_jupyter_dev.jupyter_mcp_cli \
  --mcp-url http://127.0.0.1:3001/mcp \
  read-guide --page recipes/stroke-analysis --max-chars 500 >/dev/null

docker exec "${CONTAINER}" python -m mip_jupyter_dev.jupyter_mcp_cli \
  --mcp-url http://127.0.0.1:3001/mcp \
  notebook-outline workspace/examples/feres_analysis.ipynb >/dev/null

docker exec "${CONTAINER}" sh -lc '
  if /tmp/mip-codex-home/bin/mip-shell-guard -c "cat > scratch/foo.py << EOF"; then
    echo "shell guard should reject heredocs" >&2
    exit 1
  fi
'

echo "Smoke test passed for ${IMAGE}"
