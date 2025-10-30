#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 4 ]]; then
  echo "用法: $0 <session> <strategy> <symbols逗号分隔> <objective>" >&2
  exit 1
fi

SESSION=$1
STRATEGY=$2
SYMBOLS=$3
OBJECTIVE=$4

docker run --rm \
  -e OPENAI_API_KEY="${OPENAI_API_KEY:-}" \
  -v "$(pwd)":/app \
  llm-trader/prod \
  python -m llm_trader.pipeline.auto \
    --session "${SESSION}" \
    --strategy "${STRATEGY}" \
    --symbols "${SYMBOLS}" \
    --objective "${OBJECTIVE}" \
    --backtest-start 2024-01-01 \
    --backtest-end 2024-03-01
