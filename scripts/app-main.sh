#!/bin/sh
set -eu

RESOURCES_DIR="$(cd "$(dirname "$0")/../Resources" && pwd)"
LAUNCHER="$RESOURCES_DIR/Scripts/launcher.sh"
LOG_FILE="${HOME}/Library/Application Support/双面打印助手/runtime/webapp.log"

if /bin/sh "$LAUNCHER"; then
  exit 0
fi

if [ -f "$LOG_FILE" ]; then
  /usr/bin/open -a TextEdit "$LOG_FILE" || true
fi

/usr/bin/osascript -e 'display dialog "双面打印助手启动失败，请查看日志。" buttons {"好"} default button 1 with icon stop'
exit 1
