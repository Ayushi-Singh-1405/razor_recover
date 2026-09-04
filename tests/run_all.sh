#!/usr/bin/env bash
# Revoco test runner — executes every suite in tests/.
#
#   tests/run_all.sh
#
# Requirements:
#   - Run with the project venv's python (activate it, or it falls back to
#     ./venv/bin/python).
#   - test_phase0.py additionally needs the API server running on
#     http://localhost:8000 (cd backend && ../venv/bin/uvicorn main:app --port 8000).
#     If it isn't running, that suite is skipped automatically.

set -u
cd "$(dirname "$0")/.." || exit 1

# Prefer the active interpreter; fall back to the project venv.
if command -v python >/dev/null 2>&1 && python -c "import fastapi" >/dev/null 2>&1; then
  PY="$(command -v python)"
elif [ -x "./venv/bin/python" ]; then
  PY="$(cd . && pwd)/venv/bin/python"
else
  echo "No usable python found (activate the venv first)."
  exit 2
fi

fail=0

echo "=============================================="
echo " 1/3  Agent durability (mock-based, no server)"
echo "=============================================="
"$PY" tests/test_run_agent_durability.py || fail=1

echo ""
echo "=============================================="
echo " 2/3  Dashboard summary vs source reports"
echo "      (needs Neon reachable — no server)"
echo "=============================================="
"$PY" tests/dashboard_summary_check.py || fail=1

echo ""
echo "=============================================="
echo " 3/3  Phase 0 smoke tests (live API on :8000)"
echo "=============================================="
if curl -s --max-time 2 http://localhost:8000/health >/dev/null 2>&1; then
  PYTHONPATH="$(pwd)/backend" "$PY" tests/test_phase0.py || fail=1
else
  echo "SKIP — server not running on :8000."
  echo "       Start it with: cd backend && ../venv/bin/uvicorn main:app --port 8000"
fi

echo ""
if [ "$fail" -eq 0 ]; then
  echo "ALL SUITES PASSED"
else
  echo "ONE OR MORE SUITES FAILED"
fi
exit $fail
