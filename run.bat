@echo off
rem 百炼兼容转发网关(后台运行)。
rem 用法: run.bat [start]
rem 日志写入 logs\gateway.log。
rem 停止: 在 git bash 中执行 ./run.sh stop,或 taskkill /F /IM python.exe
cd /d "%~dp0"
if not exist logs mkdir logs
start "agent-proxy-gateway" /min cmd /c "uv run python -m app.main > logs\gateway.log 2>&1"
echo Gateway started in background. Log: logs\gateway.log