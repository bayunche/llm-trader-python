#!/usr/bin/env bash
set -euo pipefail

: "${DASHBOARD_PORT:=8501}"
: "${REPORT_OUTPUT_DIR:=reports}"
: "${PIPELINE_STATUS_FILENAME:=status.json}"

PIPELINE_STATUS_DIR="${REPORT_OUTPUT_DIR%/}"
PIPELINE_STATUS_FILE="${PIPELINE_STATUS_DIR}/${PIPELINE_STATUS_FILENAME}"
mkdir -p "$(dirname "${PIPELINE_STATUS_FILE}")"

: "${LLM_TRADER_SCHEDULER_CONFIG:=config/scheduler.prod.json}"
export REPORT_OUTPUT_DIR PIPELINE_STATUS_FILENAME DASHBOARD_PORT LLM_TRADER_SCHEDULER_CONFIG

echo "[entrypoint] starting unified app (pipeline + scheduler + dashboard)"
exec python app.py
