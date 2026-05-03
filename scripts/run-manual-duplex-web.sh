#!/bin/sh
set -eu

BUNDLED_PYTHON="/Users/kupars/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"

if [ -x "$BUNDLED_PYTHON" ]; then
  exec "$BUNDLED_PYTHON" "$(dirname "$0")/../webapp/server.py"
fi

exec python3 "$(dirname "$0")/../webapp/server.py"
