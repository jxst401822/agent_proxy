@echo off
rem 启动百炼兼容转发网关(读取 .env 中的 HOST/PORT)。
rem 用法: run.bat    (Windows cmd / 双击)
cd /d "%~dp0"
uv run python -m app.main