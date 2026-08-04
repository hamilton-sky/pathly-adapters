#!/bin/bash
# Pathly Studio — dev-mode launcher (macOS counterpart to launch.bat)
cd "$(dirname "$0")" || exit 1

# VSCode's extension host exports ELECTRON_RUN_AS_NODE=1. Inherited, it makes
# Electron boot as plain Node, so `require('electron')` returns a path string
# and app.whenReady() is undefined.
unset ELECTRON_RUN_AS_NODE

# getPythonPath() (src/main/python.ts) falls back to bare `python3` in dev.
# Without the venv first on PATH that resolves to Homebrew's interpreter, where
# pathly_orchestrator isn't installed — and the FSM server dies on startup.
VENV="$(cd .. && pwd)/.venv"
if [ -x "$VENV/bin/python3" ]; then
  export PATH="$VENV/bin:$PATH"
else
  echo "warning: no venv at $VENV — the FSM server will fail to start" >&2
fi

npm run dev
