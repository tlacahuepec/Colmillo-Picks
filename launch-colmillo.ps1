<#
.SYNOPSIS
    Starts Colmillo-Picks and opens its local React UI.

.DESCRIPTION
    Intended as the target of the Windows Desktop shortcut. It starts the
    existing full-stack runner in a visible PowerShell window, waits for the
    UI to accept requests, and then opens it in the default browser.
#>

[CmdletBinding()]
param(
    [int]$StartupTimeoutSeconds = 60,
    [string]$UiUrl = "http://localhost:5173"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Runner = Join-Path $RepoRoot "run-dev.ps1"
Add-Type -AssemblyName System.Windows.Forms

if (-not (Test-Path $Runner)) {
    throw "The Colmillo-Picks runner was not found at $Runner."
}

$PowerShell = Join-Path $PSHOME "powershell.exe"
if (-not (Test-Path $PowerShell)) {
    $PowerShell = "powershell.exe"
}

Start-Process -FilePath $PowerShell -WorkingDirectory $RepoRoot -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy", "Bypass",
    "-File", $Runner
)

$Deadline = (Get-Date).AddSeconds($StartupTimeoutSeconds)
while ((Get-Date) -lt $Deadline) {
    try {
        $Response = Invoke-WebRequest -Uri $UiUrl -UseBasicParsing -TimeoutSec 2
        if ($Response.StatusCode -ge 200 -and $Response.StatusCode -lt 500) {
            Start-Process $UiUrl
            exit 0
        }
    } catch {
        # The UI is still starting; retry until the deadline.
    }

    Start-Sleep -Seconds 1
}

[System.Windows.Forms.MessageBox]::Show(
    "Colmillo-Picks did not become available at $UiUrl within $StartupTimeoutSeconds seconds. Check the launcher window for details.",
    "Colmillo-Picks startup",
    [System.Windows.Forms.MessageBoxButtons]::OK,
    [System.Windows.Forms.MessageBoxIcon]::Error
) | Out-Null
exit 1
