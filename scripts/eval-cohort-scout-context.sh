#!/usr/bin/env bash
# Offline (+ optional live) context-efficiency gate for production Cohort Scout.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

echo "Running Cohort Scout context eval..."
uv run python -m mip_jupyter_dev.cohort_scout_eval "$@"
