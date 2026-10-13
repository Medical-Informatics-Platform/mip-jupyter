#!/bin/sh
set -eu

WORK="${MIP_WORK_DIR:-/home/jovyan/work}"
TEMPLATE="${MIP_WORKSPACE_TEMPLATE:-/opt/mip-workspace-template}"
MCP_PORT="${JUPYTER_MCP_PORT:-3001}"
JUPYTER_AI_CONFIG="${JUPYTER_AI_CONFIG:-/tmp/mip-jupyter-ai-config.json}"
CODEX_HOME="${CODEX_HOME:-/tmp/mip-codex-home}"

mkdir -p "${WORK}/scratch"

if [ ! -f "${WORK}/Welcome.ipynb" ]; then
  cp -a "${TEMPLATE}/." "${WORK}/"
fi

# Shared read-only examples, mounted by the notebook operator. The link is relative, so
# resolved paths stay under the workspace (jupyter-mcp refuses anything outside it).
if [ -e "${WORK}/.mip-examples/examples" ]; then
  if [ ! -L "${WORK}/examples" ]; then
    [ ! -e "${WORK}/examples" ] || mv "${WORK}/examples" "${WORK}/examples-old"
    ln -s .mip-examples/examples "${WORK}/examples"
  fi
elif [ -L "${WORK}/examples" ]; then
  rm "${WORK}/examples"
fi

export MIP_JUPYTER_ROOT="${WORK}"
export MIP_AGENT_DOCS="${MIP_AGENT_DOCS:-/opt/mip-agent-docs}"
export JUPYTER_MCP_URL="http://127.0.0.1:${MCP_PORT}/mcp"

if [ -n "${CODEX_VLLM_BASE_URL:-}" ]; then
  rm -rf "${CODEX_HOME}"
  python -m dev.codex_bootstrap "${CODEX_HOME}" "${JUPYTER_AI_CONFIG}" --mcp-port "${MCP_PORT}"
  export CODEX_HOME
  export PATH="${CODEX_HOME}/bin:${PATH}"
  export SHELL="${CODEX_HOME}/bin/mip-shell-guard"
else
  python -m dev.jupyter_mcp_config "${JUPYTER_AI_CONFIG}" --mcp-port "${MCP_PORT}"
fi

default_notebook="${MIP_NOTEBOOK:-Welcome.ipynb}"

# Optional hub flag goes in "$@" so it stays one quoted word (or none).
set --
if [ -n "${JUPYTERHUB_SERVICE_PREFIX:-}" ]; then
  set -- "--ServerApp.base_url=${JUPYTERHUB_SERVICE_PREFIX}"
  default_url="lab/tree/${default_notebook}"
else
  default_url="/lab/tree/${default_notebook}"
fi

exec jupyter lab \
  --no-browser \
  --ServerApp.ip="${JUPYTER_HOST:-0.0.0.0}" \
  --ServerApp.port="${JUPYTER_PORT:-8888}" \
  --ServerApp.token="${JUPYTER_TOKEN:-}" \
  --ServerApp.root_dir="${WORK}" \
  --ServerApp.default_url="${default_url}" \
  "$@" \
  --YDocExtension.disable_rtc=True \
  --ServerApp.websocket_ping_interval=30000 \
  --ServerApp.websocket_ping_timeout=30000 \
  --config "${JUPYTER_AI_CONFIG}"
