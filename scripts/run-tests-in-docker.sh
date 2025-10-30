#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
COMPOSE_FILE="${PROJECT_ROOT}/docker-compose.dev.yml"

if ! command -v docker >/dev/null 2>&1; then
  echo "[错误] 未检测到 docker 命令，请先安装 Docker Desktop 或 Docker Engine。" >&2
  exit 1
fi

if ! command -v docker compose >/dev/null 2>&1 && ! command -v docker-compose >/dev/null 2>&1; then
  echo "[错误] 未检测到 docker compose，请安装 Docker Compose v2 或 v1。" >&2
  exit 1
fi

COMPOSE_BIN="docker compose"
if ! command -v docker compose >/dev/null 2>&1; then
  COMPOSE_BIN="docker-compose"
fi

${COMPOSE_BIN} -f "${COMPOSE_FILE}" build llm-trader-dev
${COMPOSE_BIN} -f "${COMPOSE_FILE}" run --rm llm-trader-dev bash -lc "pytest"
