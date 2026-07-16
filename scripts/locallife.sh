#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPOSITORY_ROOT=$(dirname -- "$SCRIPT_DIR")
API_ROOT="$REPOSITORY_ROOT/apps/api"

if [ -x "$API_ROOT/.venv/bin/python" ]; then
  PYTHON="$API_ROOT/.venv/bin/python"
else
  PYTHON="python3"
fi

cd "$API_ROOT"
exec "$PYTHON" -m app.launcher "$@"
