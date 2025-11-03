#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="docker-compose.prod.yml"

usage() {
  cat <<'EOF'
Usage: ./start.sh [command]

Commands:
  up            Build images (if needed) and start the scheduler in detached mode (default)
  down          Stop containers and remove resources
  restart       Restart the scheduler service
  logs          Tail scheduler logs
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
    ;;
  down)
    run_compose down
    ;;
  restart)
    run_compose build
    run_compose up -d
    ;;
  logs)
    if [[ -n "$SERVICE" ]]; then
      run_compose logs -f "$SERVICE"
    else
      run_compose logs -f
    fi
    ;;
  status)
    run_compose ps
    ;;
  sync-symbols)
    run_compose run --rm --entrypoint python scheduler -m llm_trader.data.pipelines.symbols
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
