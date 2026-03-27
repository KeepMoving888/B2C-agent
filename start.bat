@echo off

:: 跨境电商智能客服系统启动脚本

echo =================================
echo 跨境电商智能客服系统启动脚本
echo =================================

:: 检查Python版本
echo 检查Python版本...
python --version

:: 检查依赖
echo 检查依赖...
pip list | findstr "Flask langchain langgraph"

:: 启动应用
echo 启动应用...
echo 访问地址: http://localhost:5000
echo =================================
python src/app.py

pause