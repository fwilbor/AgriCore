#!/usr/bin/env bash
# bin/test.sh - backend test suite + frontend production build.
set -euo pipefail
source "$(dirname "$0")/_common.sh"
require_venv

info "Backend tests (pytest)"
(cd "$BACKEND" && python -m pytest -q "$@")

info "Frontend production build"
(cd "$FRONTEND" && npm run build --silent)

info "All checks passed"
