#!/bin/sh
# Launch the PACT PreToolUse hook using the repo virtualenv Python when present
# (so PyNaCl is available for envelope signing), else fall back to system python.
# stdin (the hook event JSON) is passed straight through via exec.

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
REPO_ROOT="$(cd "$PLUGIN_ROOT/../.." && pwd)"

PY="$REPO_ROOT/.venv/bin/python"
if [ ! -x "$PY" ]; then
  PY="$(command -v python3 || command -v python)"
fi

exec "$PY" "$PLUGIN_ROOT/scripts/pact_hook.py"
