<#
.SYNOPSIS
  B2C Agent - One-click startup script
.DESCRIPTION
  Auto-detect and clean port conflicts, start backend and frontend services.
  Supports params: -BackendOnly / -FrontendOnly / -NoKill
#>
param(
  [switch]$BackendOnly,
  [switch]$FrontendOnly,
  [switch]$NoKill
)

$ErrorActionPreference = 'Stop'
$PROJECT_ROOT = Split-Path -Parent $MyInvocation.MyCommand.Definition
$BACKEND_DIR = Join-Path $PROJECT_ROOT 'backend'
$FRONTEND_DIR = Join-Path $PROJECT_ROOT 'frontend'
$PYTHON = 'python'
$BACKEND_PORT = 8000
$FRONTEND_PORT = 8080

function Write-Step($msg) { Write-Host "`n[*] $msg" -ForegroundColor Cyan }
function Write-OK($msg)   { Write-Host "    [OK] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "    [!]  $msg" -ForegroundColor Yellow }
function Write-Err($msg)  { Write-Host "    [X]  $msg" -ForegroundColor Red }

function Test-PortInUse($port) {
  $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
  return $null -ne $conn -and $conn.Count -gt 0
}

function Get-PortProcess($port) {
  $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
  if ($conn) {
    $pid = $conn[0].OwningProcess
    $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
    if ($proc) {
      $cmdLine = (Get-CimInstance Win32_Process -Filter "ProcessId=$pid").CommandLine
      return @{ PID = $pid; Name = $proc.ProcessName; CmdLine = $cmdLine }
    }
  }
  return $null
}

function Clear-Port($port, $projectKeyword) {
  if ($NoKill) { return }
  $proc = Get-PortProcess $port
  if (!$proc) { return }

  $isOurProject = $proc.CmdLine -match $projectKeyword
  if ($isOurProject) {
    Write-Warn "Port $port occupied by old process of this project (PID $($proc.PID)), auto-cleaning"
    Stop-Process -Id $proc.PID -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 500
  } else {
    Write-Err "Port $port occupied by another process (PID $($proc.PID), $($proc.Name))"
    Write-Host "    CmdLine: $($proc.CmdLine.Substring(0, [Math]::Min(120, $proc.CmdLine.Length)))" -ForegroundColor DarkGray
    $choice = Read-Host "    Kill this process? (y/N)"
    if ($choice -eq 'y' -or $choice -eq 'Y') {
      Stop-Process -Id $proc.PID -Force -ErrorAction SilentlyContinue
      Start-Sleep -Milliseconds 500
      Write-OK "Killed PID $($proc.PID)"
    } else {
      Write-Err "Cannot start: port $port occupied and user declined to kill"
      exit 1
    }
  }
}

function Start-Backend {
  Write-Step "Starting backend (port $BACKEND_PORT)"
  Clear-Port $BACKEND_PORT 'B2C-agent|app\.main'

  $backendJob = Start-Job -ScriptBlock {
    param($dir, $python, $port)
    Set-Location $dir
    & $python -m uvicorn app.main:app --host 0.0.0.0 --port $port 2>&1
  } -ArgumentList $BACKEND_DIR, $PYTHON, $BACKEND_PORT

  Write-Host "    Waiting for backend..." -NoNewline
  $ready = $false
  for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    Write-Host "." -NoNewline -ForegroundColor DarkGray
    try {
      $r = Invoke-RestMethod -Uri "http://localhost:$BACKEND_PORT/health" -TimeoutSec 2
      if ($r.status -eq 'ok') {
        $ready = $true
        break
      }
    } catch { }
  }

  if ($ready) {
    Write-Host ""
    Write-OK "Backend ready: mode=$($r.mode)"
  } else {
    Write-Host ""
    Write-Err "Backend startup timeout (30s), check logs"
    Receive-Job $backendJob
    exit 1
  }
  return $backendJob
}

function Start-Frontend {
  Write-Step "Starting frontend (port $FRONTEND_PORT)"
  Clear-Port $FRONTEND_PORT 'http\.server'

  $frontendJob = Start-Job -ScriptBlock {
    param($dir, $python, $port)
    Set-Location $dir
    & $python serve.py $port 2>&1
  } -ArgumentList $FRONTEND_DIR, $PYTHON, $FRONTEND_PORT

  Start-Sleep -Seconds 1
  if (Test-PortInUse $FRONTEND_PORT) {
    Write-OK "Frontend started: http://localhost:$FRONTEND_PORT/"
  } else {
    Write-Err "Frontend startup failed"
    Receive-Job $frontendJob
    exit 1
  }
  return $frontendJob
}

# ===== Main =====
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " B2C Agent - Smart Startup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$jobs = @()

if (!$FrontendOnly) {
  $jobs += Start-Backend
}
if (!$BackendOnly) {
  $jobs += Start-Frontend
}

Write-Step "Startup complete"
Write-Host "    Backend API:  http://localhost:$BACKEND_PORT/docs" -ForegroundColor White
Write-Host "    Frontend:     http://localhost:$FRONTEND_PORT/" -ForegroundColor White
Write-Host "    Health:       http://localhost:$BACKEND_PORT/health" -ForegroundColor White
Write-Host ""
Write-Host "    Press Ctrl+C to stop all services" -ForegroundColor DarkGray
Write-Host ""

try {
  while ($jobs | Where-Object { $_.State -eq 'Running' }) {
    Start-Sleep -Seconds 1
  }
} finally {
  Write-Step "Stopping all services"
  $jobs | Stop-Job -ErrorAction SilentlyContinue
  $jobs | Remove-Job -ErrorAction SilentlyContinue
}
