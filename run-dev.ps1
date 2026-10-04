<#
.SYNOPSIS
    Easy runner script for Visual Studio Code and PowerShell to start Colmillo-Picks Full Stack.
.DESCRIPTION
    Checks prerequisites, frees occupied ports, starts the FastAPI backend (port 8000)
    and the modern React 19 UI (port 5173) by default.
    Pass -Streamlit to start the legacy Streamlit UI (port 8501) instead.
.PARAMETER ApiOnly
    Starts only the FastAPI backend service.
.PARAMETER UiOnly
    Starts only the UI service.
.PARAMETER Streamlit
    Starts the legacy Streamlit UI (port 8501) instead of the React UI (port 5173).
.PARAMETER React
    Explicit flag to start React UI (default; retained for backward compatibility).
.PARAMETER NoPortKill
    Disables automatic freeing of occupied ports.
#>
[CmdletBinding()]
param (
    [switch]$ApiOnly,
    [switch]$UiOnly,
    [switch]$Streamlit,
    [switch]$React,
    [switch]$NoPortKill,
    [int]$PortApi = 8000,
    [int]$PortUi = 0
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

if ($PortUi -eq 0) {
    if ($Streamlit) {
        $PortUi = 8501
    } else {
        $PortUi = 5173
    }
}

function Free-Port([int]$Port) {
    try {
        $conns = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
        if ($conns) {
            foreach ($conn in $conns) {
                $pidToKill = $conn.OwningProcess
                if ($pidToKill -and $pidToKill -gt 0 -and $pidToKill -ne $PID) {
                    Write-Host "[!] Port $Port is in use by PID $pidToKill. Freeing port..." -ForegroundColor Yellow
                    try {
                        taskkill /F /T /PID $pidToKill 2>$null | Out-Null
                    } catch {}
                    try {
                        Stop-Process -Id $pidToKill -Force -ErrorAction SilentlyContinue
                    } catch {}
                }
            }
            Start-Sleep -Milliseconds 600
        }
    } catch {}
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "   🐺 Colmillo-Picks Sports Intelligence Full Stack Runner   " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Detect Python
$PythonExe = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    $PythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($PythonCmd) {
        $PythonExe = $PythonCmd.Source
        Write-Host "[-] Using system Python: $PythonExe" -ForegroundColor Yellow
    } else {
        Write-Error "Python executable not found. Please create a virtualenv at .venv or add Python to PATH."
        exit 1
    }
} else {
    Write-Host "[+] Using virtualenv Python: $PythonExe" -ForegroundColor Green
}

# 2. Check .env file
$EnvFile = Join-Path $RepoRoot ".env"
$EnvExample = Join-Path $RepoRoot ".env.example"
if (-not (Test-Path $EnvFile)) {
    if (Test-Path $EnvExample) {
        Copy-Item $EnvExample $EnvFile
        Write-Host "[+] Created .env from .env.example" -ForegroundColor Green
    } else {
        Write-Host "[-] Warning: No .env or .env.example file found." -ForegroundColor Yellow
    }
}

# 3. Clean up stale ports if needed
if (-not $NoPortKill) {
    if (-not $UiOnly) { Free-Port $PortApi }
    if (-not $ApiOnly) { Free-Port $PortUi }
}

$Processes = @()

try {
    # 4. Start Backend API
    if (-not $UiOnly) {
        Write-Host "[*] Starting FastAPI Backend on http://localhost:$PortApi..." -ForegroundColor Cyan
        $ApiArgs = "-m uvicorn services.api.main:app --reload --port $PortApi"
        $ApiProcess = Start-Process -FilePath $PythonExe -ArgumentList $ApiArgs -WorkingDirectory $RepoRoot -PassThru
        $Processes += $ApiProcess
        Write-Host "[+] API running (PID: $($ApiProcess.Id)) -> http://localhost:$PortApi" -ForegroundColor Green
        Write-Host "    Swagger Docs: http://localhost:$PortApi/docs" -ForegroundColor DarkCyan
    }

    # 5. Start Frontend UI
    if (-not $ApiOnly) {
        if ($Streamlit) {
            Write-Host "[*] Starting legacy Streamlit UI on http://localhost:$PortUi..." -ForegroundColor Cyan
            $StreamlitArgs = "-m streamlit run services/ui/app.py --server.port $PortUi"
            $UiProcess = Start-Process -FilePath $PythonExe -ArgumentList $StreamlitArgs -WorkingDirectory $RepoRoot -PassThru
            $Processes += $UiProcess
            Write-Host "[+] Streamlit UI running (PID: $($UiProcess.Id)) -> http://localhost:$PortUi" -ForegroundColor Green
        } else {
            $FrontendDir = Join-Path $RepoRoot "frontend"
            $NodeModules = Join-Path $FrontendDir "node_modules"
            if (-not (Test-Path $NodeModules)) {
                Write-Host "[*] Installing frontend dependencies (npm install)..." -ForegroundColor Yellow
                Start-Process -FilePath "npm" -ArgumentList "install" -WorkingDirectory $FrontendDir -Wait -NoNewWindow
            }

            Write-Host "[*] Starting React 19 UI (Vite) on http://localhost:$PortUi..." -ForegroundColor Cyan
            $NpmCmd = if ($IsWindows -or $env:OS -match "Windows") { "npm.cmd" } else { "npm" }
            $UiProcess = Start-Process -FilePath $NpmCmd -ArgumentList "run dev -- --port $PortUi" -WorkingDirectory $FrontendDir -PassThru
            $Processes += $UiProcess
            Write-Host "[+] React UI running (PID: $($UiProcess.Id)) -> http://localhost:$PortUi" -ForegroundColor Green
        }
    }

    Write-Host ""
    Write-Host "------------------------------------------------------------" -ForegroundColor DarkGray
    Write-Host " Servers are live! Press Ctrl+C in this window to stop both. " -ForegroundColor Yellow
    Write-Host " UI:       http://localhost:$PortUi" -ForegroundColor Green
    Write-Host " API Docs: http://localhost:$PortApi/docs" -ForegroundColor Cyan
    Write-Host "------------------------------------------------------------" -ForegroundColor DarkGray
    Write-Host ""

    # Keep script running until user interrupts or process exits
    while ($true) {
        Start-Sleep -Seconds 1
        foreach ($proc in $Processes) {
            if ($proc.HasExited) {
                Write-Host "[-] Process $($proc.Id) terminated (exit code: $($proc.ExitCode))." -ForegroundColor Red
                break 2
            }
        }
    }
}
finally {
    Write-Host ""
    Write-Host "[*] Stopping background processes..." -ForegroundColor Yellow
    foreach ($proc in $Processes) {
        if ($proc -and -not $proc.HasExited) {
            try {
                taskkill /F /T /PID $proc.Id 2>$null | Out-Null
            } catch {}
            try {
                Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
            } catch {}
            Write-Host "[+] Stopped process tree for PID $($proc.Id)" -ForegroundColor DarkGray
        }
    }
    if (-not $NoPortKill) {
        if (-not $UiOnly) { Free-Port $PortApi }
        if (-not $ApiOnly) { Free-Port $PortUi }
    }
    Write-Host "[+] Clean shutdown complete." -ForegroundColor Green
}
