@echo off
cd /d "E:\AI大模型开发项目\面试项目\multilang-cs-platform\backend"
"C:\Users\Windows\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\vm\tools\python\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 9000
