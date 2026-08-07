#!/usr/bin/env bash
# 启动百炼兼容转发网关(读取 .env 中的 HOST/PORT)。
# 用法: ./run.sh   (git bash / Linux / macOS)
set -euo pipefail
cd "$(dirname "$0")"
uv run python -m app.main