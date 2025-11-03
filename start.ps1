param(
    [string]$Command = "up",
    [string]$Service
)

$composeFile = "docker-compose.prod.yml"

function Show-Usage {
    @"
Usage: ./start.ps1 -Command <up|down|restart|logs|status|sync-symbols|help>

Commands:
  up            Build images (if needed) and start the llm-trader container (default)
  down          Stop containers and remove resources
  restart       Rebuild and restart the llm-trader container
  logs          Tail container logs (default llm-trader)
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
        $reportRoot = $env:REPORT_OUTPUT_DIR
        if (-not $reportRoot -and (Test-Path ".env")) {
            $line = Get-Content ".env" | Where-Object { $_ -match '^REPORT_OUTPUT_DIR=' } | Select-Object -Last 1
            if ($line) { $reportRoot = $line.Split('=')[1] }
        }
        if (-not $reportRoot) { $reportRoot = "reports" }
        $reportRoot = $reportRoot.TrimEnd('/','\')
        Write-Host "[start.ps1] pipeline status file: $reportRoot/status.json (mounted with container)"
    }
    "down" {
        Invoke-Compose -ComposeArgs @("down")
    }
    "restart" {
        Invoke-Compose -ComposeArgs @("build")
        Invoke-Compose -ComposeArgs @("up", "-d")
        $reportRoot = $env:REPORT_OUTPUT_DIR
        if (-not $reportRoot -and (Test-Path ".env")) {
            $line = Get-Content ".env" | Where-Object { $_ -match '^REPORT_OUTPUT_DIR=' } | Select-Object -Last 1
            if ($line) { $reportRoot = $line.Split('=')[1] }
        }
        if (-not $reportRoot) { $reportRoot = "reports" }
        $reportRoot = $reportRoot.TrimEnd('/','\')
        Write-Host "[start.ps1] pipeline status file: $reportRoot/status.json (mounted with container)"
    }
    "logs" {
        if ($null -ne $Service -and $Service -ne "") {
            Invoke-Compose -ComposeArgs @("logs", "-f", $Service)
        } else {
            Invoke-Compose -ComposeArgs @("logs", "-f", "llm-trader")
        }
    }
    "status" {
        Invoke-Compose -ComposeArgs @("ps")
    }
    "sync-symbols" {
        Invoke-Compose -ComposeArgs @("run", "--rm", "--entrypoint", "python", "llm-trader", "-m", "llm_trader.data.pipelines.symbols")
    }
    "help" { Show-Usage }
    default {
        Write-Host "[ERROR] Unknown command: $Command" -ForegroundColor Red
        Show-Usage
        exit 1
    }
}
