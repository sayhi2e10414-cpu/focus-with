#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

find_python() {
  if [[ -n "${PYTHON_BIN:-}" ]]; then
    printf '%s' "$PYTHON_BIN"
    return
  fi
  local candidate
  for candidate in python3.13 python3.12 python3.11 python3; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
      command -v "$candidate"
      return
    fi
  done
  echo "Focus requires Python 3.11 or newer. Ask your installation agent to install a current Python, then rerun this script." >&2
  exit 1
}

PYTHON_BIN="$(find_python)"

cd "$ROOT"

"$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)'

if [[ ! -x .venv/bin/python ]]; then
  "$PYTHON_BIN" -m venv .venv
fi

.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/setup_env.py
.venv/bin/python -c 'from app.database import Base, engine; import app.models; Base.metadata.create_all(engine)'
chmod +x scripts/focus scripts/focus-mcp scripts/install.sh scripts/deploy_remote.sh

./scripts/focus doctor

printf '\nFocusWith is installed. Start it with:\n  ./scripts/focus start\n\n'
