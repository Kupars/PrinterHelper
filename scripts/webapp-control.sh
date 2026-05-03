#!/bin/sh
set -eu

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP_SUPPORT_DIR="${HOME}/Library/Application Support/双面打印助手"
LOG_DIR="$APP_SUPPORT_DIR/runtime"
PID_FILE="$LOG_DIR/webapp.pid"
LOG_FILE="$LOG_DIR/webapp.log"
URL="http://127.0.0.1:8765/"
CURL_BIN="/usr/bin/curl"
OPEN_BIN="/usr/bin/open"
NOHUP_BIN="/usr/bin/nohup"
SLEEP_BIN="/bin/sleep"
KILL_BIN="/bin/kill"
SH_BIN="/bin/sh"
LSOF_BIN="/usr/sbin/lsof"
PGREP_BIN="/usr/bin/pgrep"

mkdir -p "$LOG_DIR"

is_server_responding() {
  "$CURL_BIN" -fsS "$URL" >/dev/null 2>&1
}

find_server_pid() {
  if [ -x "$LSOF_BIN" ]; then
    PID="$("$LSOF_BIN" -ti tcp:8765 -sTCP:LISTEN 2>/dev/null | head -n 1 || true)"
    if [ -n "${PID:-}" ]; then
      printf '%s\n' "$PID"
      return 0
    fi
  fi

  if [ -x "$PGREP_BIN" ]; then
    PID="$("$PGREP_BIN" -f "/webapp/server.py" 2>/dev/null | head -n 1 || true)"
    if [ -n "${PID:-}" ]; then
      printf '%s\n' "$PID"
      return 0
    fi
  fi

  return 1
}

adopt_running_server() {
  PID="$(find_server_pid || true)"
  if [ -n "${PID:-}" ]; then
    echo "$PID" >"$PID_FILE"
    return 0
  fi
  return 1
}

cleanup_stale_pid() {
  if [ -f "$PID_FILE" ]; then
    PID="$(cat "$PID_FILE" 2>/dev/null || true)"
    if [ -z "${PID:-}" ] || ! "$KILL_BIN" -0 "$PID" 2>/dev/null; then
      rm -f "$PID_FILE"
    fi
  fi
}

start_server() {
  cleanup_stale_pid

  if is_server_responding; then
    adopt_running_server || true
    echo "already-running"
    return 0
  fi

  : >"$LOG_FILE"
  "$NOHUP_BIN" "$SH_BIN" "$PROJECT_ROOT/scripts/run-manual-duplex-web.sh" </dev/null >"$LOG_FILE" 2>&1 &
  PID=$!
  echo "$PID" >"$PID_FILE"

  ATTEMPT=0
  while [ "$ATTEMPT" -lt 30 ]; do
    if is_server_responding; then
      adopt_running_server || true
      echo "started"
      return 0
    fi
    if ! "$KILL_BIN" -0 "$PID" 2>/dev/null; then
      echo "failed"
      return 1
    fi
    ATTEMPT=$((ATTEMPT + 1))
    "$SLEEP_BIN" 1
  done

  echo "timeout"
  return 1
}

stop_server() {
  cleanup_stale_pid

  PID=""
  if [ -f "$PID_FILE" ]; then
    PID="$(cat "$PID_FILE" 2>/dev/null || true)"
  fi

  if [ -z "${PID:-}" ]; then
    PID="$(find_server_pid || true)"
  fi

  if [ -z "${PID:-}" ]; then
    rm -f "$PID_FILE"
    echo "not-running"
    return 0
  fi

  if "$KILL_BIN" -0 "$PID" 2>/dev/null; then
    "$KILL_BIN" "$PID" || true
  fi

  ATTEMPT=0
  while [ "$ATTEMPT" -lt 10 ]; do
    if ! "$KILL_BIN" -0 "$PID" 2>/dev/null; then
      break
    fi
    ATTEMPT=$((ATTEMPT + 1))
    "$SLEEP_BIN" 1
  done

  if "$KILL_BIN" -0 "$PID" 2>/dev/null; then
    "$KILL_BIN" -9 "$PID" || true
  fi

  rm -f "$PID_FILE"
  echo "stopped"
}

status_server() {
  cleanup_stale_pid
  if is_server_responding; then
    adopt_running_server || true
    echo "running"
    return 0
  fi
  rm -f "$PID_FILE"
  echo "stopped"
  return 1
}

open_browser() {
  "$OPEN_BIN" "$URL"
}

show_log() {
  if [ -f "$LOG_FILE" ]; then
    "$OPEN_BIN" -a TextEdit "$LOG_FILE"
  fi
}

COMMAND="${1:-}"

case "$COMMAND" in
  start)
    start_server
    ;;
  stop)
    stop_server
    ;;
  status)
    status_server
    ;;
  open)
    open_browser
    ;;
  show-log)
    show_log
    ;;
  *)
    echo "Usage: $0 {start|stop|status|open|show-log}" >&2
    exit 1
    ;;
esac
