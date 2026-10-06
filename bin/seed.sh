#!/usr/bin/env bash
# bin/seed.sh - (re)create tables and load deterministic mock data.
#
#   bin/seed.sh                         seed the DATABASE_URL from backend/.env
#   bin/seed.sh --database-url URL      seed another database (e.g. AWS RDS)
#   bin/seed.sh --files-only            only re-upload service-report files to S3
#   bin/seed.sh --yes                   skip the confirmation prompt
set -euo pipefail
source "$(dirname "$0")/_common.sh"

FILES_ONLY=""; ASSUME_YES=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --database-url) export DATABASE_URL="$2"; shift 2 ;;
    --files-only)   FILES_ONLY="--files-only"; shift ;;
    -y|--yes)       ASSUME_YES=1; shift ;;
    -h|--help)      sed -n '2,8p' "$0"; exit 0 ;;
    *) die "Unknown option: $1" ;;
  esac
done

require_venv
target="$(env_value DATABASE_URL | sed -E 's#//([^:]+):[^@]*@#//\1:****@#')"

if [[ -z "$FILES_ONLY" && -z "$ASSUME_YES" && -t 0 ]]; then
  warn "This DROPS and recreates every table in: $target"
  read -r -p "Continue? [y/N] " answer
  [[ "$answer" =~ ^[Yy]$ ]] || die "Aborted"
fi

ensure_s3_emulator
info "Seeding $target"
cd "$BACKEND" && python -m app.seed $FILES_ONLY
