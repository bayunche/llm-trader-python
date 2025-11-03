param(
    [string]$Command = "up",
    [string]$Service
)

$composeFile = "docker-compose.prod.yml"

function Show-Usage {
    @"
Usage: ./start.ps1 -Command <up|down|restart|logs|status|sync-symbols|help>

Commands:
  up            Build images (if needed) and start the scheduler in detached mode (default)
  down          Stop containers and remove resources
  restart       Rebuild and restart the scheduler service
  logs          Tail scheduler logs
  status        Show current container status
  sync-symbols  Refresh securities universe via symbols pipeline (runs inside container)
  help          Show this help message
"@
}

function Invoke-Compose {
    param([string[]]$ComposeArgs)
    docker compose -f $composeFile @ComposeArgs
}

switch ($Command.ToLower()) {
    "up" {
        Invoke-Compose -ComposeArgs @("build")
        Invoke-Compose -ComposeArgs @("up", "-d")
    }
    "down" {
        Invoke-Compose -ComposeArgs @("down")
    }
    "restart" {
        Invoke-Compose -ComposeArgs @("build")
        Invoke-Compose -ComposeArgs @("up", "-d")
    }
    "logs" {
        if ($null -ne $Service -and $Service -ne "") {
            Invoke-Compose -ComposeArgs @("logs", "-f", $Service)
        } else {
            Invoke-Compose -ComposeArgs @("logs", "-f")
        }
    }
    "status" {
        Invoke-Compose -ComposeArgs @("ps")
    }
    "sync-symbols" {
        Invoke-Compose -ComposeArgs @("run", "--rm", "--entrypoint", "python", "scheduler", "-m", "llm_trader.data.pipelines.symbols")
    }
    "help" { Show-Usage }
    default {
        Write-Host "[ERROR] Unknown command: $Command" -ForegroundColor Red
        Show-Usage
        exit 1
    }
}
