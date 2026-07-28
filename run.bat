@echo off
REM ============================================
REM  B2C Agent - Backend Startup Script
REM  Usage: run.bat [port]
REM ============================================
cd /d "%~dp0backend"
python -m uvicorn app.main:app --host 0.0.0.0 --port %1
