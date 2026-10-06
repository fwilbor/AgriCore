#!/usr/bin/env bash
# bin/start.sh - run the whole stack locally with one command.
#   S3 emulator  http://localhost:5001
#   API          http://localhost:8000   (Swagger docs at /docs)
#   Frontend     http://localhost:5173
# Ctrl+C stops everything.
set -euo pipefail
source "$(dirname "$0")/_common.sh"
require_venv

# After a reboot or crash, Postgres can take a while to finish recovery.
# Starting the API before it's ready makes the API crash at startup, so wait.
if ! pg_isready -q 2>/dev/null; then
  info "Waiting for PostgreSQL to accept connections..."
  for _ in $(seq 1 60); do pg_isready -q 2>/dev/null && break; sleep 1; done
  pg_isready -q 2>/dev/null || die "PostgreSQL is not running. Start it with: brew services start postgresql@16"
fi
port_open 8000 && die "Port 8000 is busy - is the API already running? (lsof -i :8000)"
port_open 5173 && die "Port 5173 is busy - is the frontend already running? (lsof -i :5173)"

ensure_s3_emulator
# The emulator keeps files in memory, so restore seeded report files on every start.
(cd "$BACKEND" && python -m app.seed --files-only) || warn "No data yet - run bin/seed.sh"

pids=()
cleanup() {
  echo; info "Stopping AgriCore..."
  [[ ${#pids[@]} -gt 0 ]] && kill "${pids[@]}" 2>/dev/null || true
  if [[ -f "$RUN_DIR/moto.pid" ]]; then kill "$(cat "$RUN_DIR/moto.pid")" 2>/dev/null || true; rm -f "$RUN_DIR/moto.pid"; fi
}
trap cleanup EXIT INT TERM

info "Starting API on http://localhost:8000"
(cd "$BACKEND" && exec uvicorn app.main:app --reload --port 8000) &
pids+=($!)

info "Starting frontend on http://localhost:5173"
(cd "$FRONTEND" && exec npm run dev -- --port 5173 --strictPort) &
pids+=($!)

sleep 3
echo
echo "${c_bold}AgriCore is running${c_off}"
echo "  App        http://localhost:5173"
echo "  API docs   http://localhost:8000/docs"
echo "  Logins     admin@ / farmhand@ / auditor@prairiecrest.coop   password: AgriCore2026!"
echo "  Ctrl+C to stop"
wait
