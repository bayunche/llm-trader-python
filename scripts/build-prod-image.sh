#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

if ! command -v docker >/dev/null 2>&1; then
  echo "[错误] 未检测到 docker 命令。" >&2
  exit 1
fi

docker build -t llm-trader/prod -f "${PROJECT_ROOT}/Dockerfile" "${PROJECT_ROOT}"
