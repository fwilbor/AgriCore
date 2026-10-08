#!/usr/bin/env bash
# Shared helpers sourced by the other bin/ scripts. Not meant to be run directly.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
VENV="$BACKEND/.venv"
RUN_DIR="$ROOT/.run"          # pid + log files for background processes
mkdir -p "$RUN_DIR"

c_green=$'\033[32m'; c_yellow=$'\033[33m'; c_red=$'\033[31m'; c_bold=$'\033[1m'; c_off=$'\033[0m'
info() { echo "${c_green}==>${c_off} ${c_bold}$*${c_off}"; }
warn() { echo "${c_yellow}!!  $*${c_off}"; }
die()  { echo "${c_red}xx  $*${c_off}" >&2; exit 1; }

require_venv() {
  [[ -x "$VENV/bin/python" ]] || die "Python venv missing - run bin/setup.sh first"
  # shellcheck disable=SC1091
  source "$VENV/bin/activate"
}

# Read KEY from backend/.env (env var wins if already set).
env_value() {
  local key="$1"
  # An exported variable wins, even when set to "" (e.g. S3_ENDPOINT_URL= for real AWS).
  if printenv "$key" >/dev/null 2>&1; then printenv "$key"; return; fi
  grep -E "^${key}=" "$BACKEND/.env" 2>/dev/null | tail -1 | cut -d= -f2-
}

port_open() { (echo >"/dev/tcp/127.0.0.1/$1") >/dev/null 2>&1; }

# If S3_ENDPOINT_URL points at localhost, make sure the moto S3 emulator is running.
ensure_s3_emulator() {
  local endpoint port
  endpoint="$(env_value S3_ENDPOINT_URL)"
  [[ "$endpoint" =~ ^http://(localhost|127\.0\.0\.1):([0-9]+) ]] || return 0  # real AWS
  port="${BASH_REMATCH[2]}"
  if port_open "$port"; then return 0; fi
  info "Starting local S3 emulator (moto) on :$port"
  nohup "$VENV/bin/moto_server" -H 127.0.0.1 -p "$port" >"$RUN_DIR/moto.log" 2>&1 &
  echo $! >"$RUN_DIR/moto.pid"
  for _ in $(seq 1 30); do port_open "$port" && return 0; sleep 0.3; done
  die "S3 emulator did not start - see $RUN_DIR/moto.log"
}
