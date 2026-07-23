<#
.SYNOPSIS
  多语言多平台智能客服系统 - 一键智能启动脚本
.DESCRIPTION
  自动检测并清理端口冲突，启动后端和前端服务
  支持参数：-BackendOnly / -FrontendOnly / -NoKill
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
$PYTHON = 'C:\Users\Windows\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\vm\tools\python\python.exe'
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
    Write-Warn "端口 $port 被本项目旧进程占用 (PID $($proc.PID))，自动清理"
    Stop-Process -Id $proc.PID -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 500
  } else {
    Write-Err "端口 $port 被其他项目占用 (PID $($proc.PID), $($proc.Name))"
    Write-Host "    命令行: $($proc.CmdLine.Substring(0, [Math]::Min(120, $proc.CmdLine.Length)))" -ForegroundColor DarkGray
    $choice = Read-Host "    是否终止该进程? (y/N)"
    if ($choice -eq 'y' -or $choice -eq 'Y') {
      Stop-Process -Id $proc.PID -Force -ErrorAction SilentlyContinue
      Start-Sleep -Milliseconds 500
      Write-OK "已终止 PID $($proc.PID)"
    } else {
      Write-Err "无法启动：端口 $port 被占用且用户拒绝终止"
      exit 1
    }
  }
}

function Start-Backend {
  Write-Step "启动后端服务 (端口 $BACKEND_PORT)"
  Clear-Port $BACKEND_PORT 'multilang-cs-platform|app\.main'

  $backendJob = Start-Job -ScriptBlock {
    param($dir, $python, $port)
    Set-Location $dir
    & $python -m uvicorn app.main:app --host 0.0.0.0 --port $port 2>&1
  } -ArgumentList $BACKEND_DIR, $PYTHON, $BACKEND_PORT

  # 等待后端就绪（最多30秒）
  Write-Host "    等待后端启动..." -NoNewline
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
    Write-OK "后端已就绪: mode=$($r.mode)"
  } else {
    Write-Host ""
    Write-Err "后端启动超时（30秒），请检查日志"
    Receive-Job $backendJob
    exit 1
  }
  return $backendJob
}

function Start-Frontend {
  Write-Step "启动前端服务 (端口 $FRONTEND_PORT)"
  Clear-Port $FRONTEND_PORT 'http\.server'

  $frontendJob = Start-Job -ScriptBlock {
    param($dir, $python, $port)
    Set-Location $dir
    # 使用 serve.py（禁用缓存），确保JS/CSS修改立即生效
    & $python serve.py $port 2>&1
  } -ArgumentList $FRONTEND_DIR, $PYTHON, $FRONTEND_PORT

  Start-Sleep -Seconds 1
  if (Test-PortInUse $FRONTEND_PORT) {
    Write-OK "前端已启动: http://localhost:$FRONTEND_PORT/"
  } else {
    Write-Err "前端启动失败"
    Receive-Job $frontendJob
    exit 1
  }
  return $frontendJob
}

# ===== 主流程 =====
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " 多语言多平台智能客服系统 - 智能启动" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$jobs = @()

if (!$FrontendOnly) {
  $jobs += Start-Backend
}
if (!$BackendOnly) {
  $jobs += Start-Frontend
}

Write-Step "启动完成"
Write-Host "    后端 API:  http://localhost:$BACKEND_PORT/docs" -ForegroundColor White
Write-Host "    前端页面:  http://localhost:$FRONTEND_PORT/" -ForegroundColor White
Write-Host "    健康检查:  http://localhost:$BACKEND_PORT/health" -ForegroundColor White
Write-Host ""
Write-Host "    按 Ctrl+C 停止所有服务" -ForegroundColor DarkGray
Write-Host ""

# 保持运行，直到用户按Ctrl+C
try {
  while ($jobs | Where-Object { $_.State -eq 'Running' }) {
    Start-Sleep -Seconds 1
  }
} finally {
  Write-Step "停止所有服务"
  $jobs | Stop-Job -ErrorAction SilentlyContinue
  $jobs | Remove-Job -ErrorAction SilentlyContinue
}
