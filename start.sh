#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="docker-compose.prod.yml"

usage() {
  cat <<'EOF'
Usage: ./start.sh [command]

Commands:
  up            Build images (if needed) and start the llm-trader container（默认）
  down          Stop containers and remove resources
  restart       Restart the llm-trader container
  logs          Tail container logs（默认 llm-trader）
  status        Show current container status
  sync-symbols  Refresh securities universe via symbols pipeline (runs inside container)
  help          Show this help message
EOF
}

run_compose() {
  docker compose -f "$COMPOSE_FILE" "$@"
}

COMMAND=${1:-up}
SERVICE=${2:-}

case "$COMMAND" in
  up)
    run_compose build
    run_compose up -d
    STATUS_ROOT="${REPORT_OUTPUT_DIR:-}"
    if [[ -z "${STATUS_ROOT}" && -f ".env" ]]; then
      STATUS_ROOT=$(grep -E '^REPORT_OUTPUT_DIR=' .env | tail -n 1 | cut -d'=' -f2-)
    fi
    STATUS_ROOT=${STATUS_ROOT:-reports}
    echo "[start.sh] pipeline status file: ${STATUS_ROOT%/}/status.json （与容器挂载目录同步）"
    ;;
  down)
    run_compose down
    ;;
  restart)
    run_compose build
    run_compose up -d
    STATUS_ROOT="${REPORT_OUTPUT_DIR:-}"
    if [[ -z "${STATUS_ROOT}" && -f ".env" ]]; then
      STATUS_ROOT=$(grep -E '^REPORT_OUTPUT_DIR=' .env | tail -n 1 | cut -d'=' -f2-)
    fi
    STATUS_ROOT=${STATUS_ROOT:-reports}
    echo "[start.sh] pipeline status file: ${STATUS_ROOT%/}/status.json （与容器挂载目录同步）"
    ;;
  logs)
    if [[ -n "$SERVICE" ]]; then
      run_compose logs -f "$SERVICE"
    else
      run_compose logs -f llm-trader
    fi
    ;;
  status)
    run_compose ps
    ;;
  sync-symbols)
    run_compose run --rm --entrypoint python llm-trader -m llm_trader.data.pipelines.symbols
    ;;
  help|-h|--help)
    usage
    ;;
  *)
    echo "[ERROR] Unknown command: $COMMAND" >&2
    usage
    exit 1
    ;;
esac
