#!/usr/bin/env bash
# Run all five deployment steps in order. Each step is safe to re-run.
set -euo pipefail
DIR="$(dirname "$0")"
"$DIR/1-database.sh"
"$DIR/2-storage.sh"
"$DIR/3-seed.sh"
"$DIR/4-backend.sh"
"$DIR/5-frontend.sh"
