#!/usr/bin/env bash
# Return PickGlobal data, config, and traffic to the CloudBase document baseline.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}:${ROOT}/backend${PYTHONPATH:+:$PYTHONPATH}"
if [[ -x "$ROOT/backend/.venv/bin/python" ]]; then
  PY="$ROOT/backend/.venv/bin/python"
elif command -v python3.12 >/dev/null 2>&1; then
  PY="$(command -v python3.12)"
else
  PY="python3"
fi
exec "$PY" -m rollback "$@"
