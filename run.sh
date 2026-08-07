#!/usr/bin/env bash
# 百炼兼容转发网关启动/停止脚本(后台运行)。
#
# 用法:
#   ./run.sh           启动(后台)
#   ./run.sh start     启动(后台)
#   ./run.sh stop      停止
#   ./run.sh status    查看运行状态
#   ./run.sh restart   重启
#
# 监听地址与端口取自 .env 的 HOST/PORT;日志写入 logs/gateway.log。
set -euo pipefail
cd "$(dirname "$0")"

CMD="uv run python -m app.main"
LOG="logs/gateway.log"
PID_FILE=".gateway.pid"

mkdir -p logs

pid_alive() { [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; }

start() {
  if pid_alive; then
    echo "Gateway already running (PID $(cat "$PID_FILE"))."
    return 0
  fi
  nohup $CMD > "$LOG" 2>&1 &
  echo $! > "$PID_FILE"
  echo "Gateway started in background. PID $(cat "$PID_FILE"). Log: $LOG"
}

stop() {
  if ! [ -f "$PID_FILE" ]; then
    echo "No PID file; nothing to stop."
    return 0
  fi
  local pid
  pid=$(cat "$PID_FILE")
  if kill -0 "$pid" 2>/dev/null; then
    kill "$pid" && echo "Stopped gateway (PID $pid)."
  else
    echo "Process $pid not running; removing stale PID file."
  fi
  rm -f "$PID_FILE"
}

status() {
  if pid_alive; then
    echo "Gateway running (PID $(cat "$PID_FILE"))."
  else
    echo "Gateway not running."
  fi
}

case "${1:-start}" in
  start)   start ;;
  stop)    stop ;;
  status)  status ;;
  restart) stop; sleep 1; start ;;
  *) echo "Usage: $0 [start|stop|status|restart]"; exit 1 ;;
esac