#!/usr/bin/env bash
set -euo pipefail

: "${DASHBOARD_PORT:=8501}"
: "${REPORT_OUTPUT_DIR:=reports}"
: "${PIPELINE_STATUS_FILENAME:=status.json}"

PIPELINE_STATUS_DIR="${REPORT_OUTPUT_DIR%/}"
PIPELINE_STATUS_FILE="${PIPELINE_STATUS_DIR}/${PIPELINE_STATUS_FILENAME}"
mkdir -p "$(dirname "${PIPELINE_STATUS_FILE}")"

echo "[entrypoint] running full automation pipeline..."
PIPELINE_EXIT_CODE=0
if python3 scripts/run_full_pipeline.py; then
  echo "[entrypoint] pipeline execution finished (exit=0)"
else
  PIPELINE_EXIT_CODE=$?
  echo "[entrypoint] pipeline exited with code ${PIPELINE_EXIT_CODE}, will continue to serve dashboard" >&2
fi

if [[ -f "${PIPELINE_STATUS_FILE}" ]]; then
  echo "[entrypoint] pipeline status recorded at ${PIPELINE_STATUS_FILE}"
else
  echo "[entrypoint] warning: pipeline status file not found at ${PIPELINE_STATUS_FILE}" >&2
fi

export LLM_TRADER_PIPELINE_STATUS="${PIPELINE_STATUS_FILE}"
export LLM_TRADER_PIPELINE_EXIT_CODE="${PIPELINE_EXIT_CODE}"

echo "[entrypoint] starting dashboard on port ${DASHBOARD_PORT}"
exec streamlit run dashboard/app.py \
  --server.address=0.0.0.0 \
  --server.port="${DASHBOARD_PORT}" \
  --server.headless=true
