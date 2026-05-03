#!/bin/sh
set -eu

APP_SUPPORT_DIR="${HOME}/Library/Application Support/双面打印助手"
RUNTIME_DIR="$APP_SUPPORT_DIR/runtime"
APP_DATA_DIR="$APP_SUPPORT_DIR/app"
PAYLOAD_DIR="$APP_DATA_DIR/AppPayload"
WEBAPP_DIR="$PAYLOAD_DIR/webapp"
SCRIPTS_DIR="$PAYLOAD_DIR/scripts"
LOG_FILE="$RUNTIME_DIR/webapp.log"
PID_FILE="$RUNTIME_DIR/webapp.pid"
URL="http://127.0.0.1:8765/"
BUNDLED_PYTHON="/Users/kupars/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"
BUNDLE_RESOURCES_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PAYLOAD_SOURCE_DIR="$BUNDLE_RESOURCES_DIR/AppPayload"

mkdir -p "$RUNTIME_DIR"
mkdir -p "$APP_DATA_DIR"

if /usr/bin/curl -fsS "$URL" >/dev/null 2>&1; then
  /usr/bin/open "$URL"
  exit 0
fi

PYTHON_BIN="$BUNDLED_PYTHON"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="python3"
fi

if [ ! -d "$PAYLOAD_SOURCE_DIR/webapp" ] || [ ! -d "$PAYLOAD_SOURCE_DIR/scripts" ]; then
  exit 1
fi

/bin/rm -rf "$PAYLOAD_DIR"
/usr/bin/ditto "$PAYLOAD_SOURCE_DIR" "$PAYLOAD_DIR"

CONTROL_SCRIPT="$SCRIPTS_DIR/webapp-control.sh"
/bin/chmod +x "$CONTROL_SCRIPT" "$SCRIPTS_DIR/run-manual-duplex-web.sh"

/bin/sh "$CONTROL_SCRIPT" start >/dev/null
if [ -f "$PID_FILE" ]; then
  PID="$(cat "$PID_FILE" 2>/dev/null || true)"
else
  PID=""
fi

ATTEMPT=0
while [ "$ATTEMPT" -lt 30 ]; do
  if /usr/bin/curl -fsS "$URL" >/dev/null 2>&1; then
    /usr/bin/open "$URL"
    exit 0
  fi
  if ! /bin/kill -0 "$PID" 2>/dev/null; then
    break
  fi
  ATTEMPT=$((ATTEMPT + 1))
  /bin/sleep 1
done

exit 1
