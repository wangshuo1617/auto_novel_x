#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

PYTHON_BIN="${PYTHON_BIN:-${REPO_DIR}/.venv/bin/python}"
STREAMLIT_ADDRESS="${STREAMLIT_ADDRESS:-0.0.0.0}"
STREAMLIT_PORT="${STREAMLIT_PORT:-8501}"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Python executable not found: ${PYTHON_BIN}" >&2
  echo "Run 'uv sync' or set PYTHON_BIN to a valid interpreter." >&2
  exit 1
fi

cd "${REPO_DIR}"

exec "${PYTHON_BIN}" -m streamlit run frontend/app.py \
  --server.headless true \
  --server.address "${STREAMLIT_ADDRESS}" \
  --server.port "${STREAMLIT_PORT}" \
  --browser.gatherUsageStats false
