#!/usr/bin/env bash
# bin/setup.sh - install dependencies and initialise the local environment.
#   * picks a Python >= 3.10, creates backend/.venv, installs requirements.txt
#   * installs frontend npm packages
#   * creates backend/.env and frontend/.env (random JWT secret)
#   * creates the local PostgreSQL role + databases if Postgres is running
set -euo pipefail
source "$(dirname "$0")/_common.sh"

# ---------------------------------------------------------------- Python
info "Locating Python 3.10+"
PY=""
for candidate in python3.12 python3.11 python3.10 python3.13 python3; do
  if command -v "$candidate" >/dev/null 2>&1 &&
     "$candidate" -c 'import sys; sys.exit(0 if (3,10) <= sys.version_info[:2] < (3,14) else 1)' 2>/dev/null; then
    PY="$candidate"; break
  fi
done
[[ -n "$PY" ]] || die "Python 3.10-3.13 is required (brew install python@3.12)"
echo "    using $($PY --version) ($(command -v "$PY"))"

if [[ ! -x "$VENV/bin/python" ]]; then
  info "Creating virtual environment backend/.venv"
  "$PY" -m venv "$VENV"
fi
info "Installing Python packages"
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet -r "$BACKEND/requirements.txt"

# ---------------------------------------------------------------- .env files
if [[ ! -f "$BACKEND/.env" ]]; then
  info "Creating backend/.env"
  secret="$("$VENV/bin/python" -c 'import secrets; print(secrets.token_urlsafe(48))')"
  sed "s|^JWT_SECRET=.*|JWT_SECRET=$secret|" "$BACKEND/.env.example" >"$BACKEND/.env"
else
  echo "    backend/.env already exists - leaving it alone"
fi
if [[ ! -f "$FRONTEND/.env" ]]; then
  cp "$FRONTEND/.env.example" "$FRONTEND/.env"
fi

# ---------------------------------------------------------------- Node
command -v npm >/dev/null 2>&1 || die "Node.js 20+ / npm is required (brew install node)"
info "Installing frontend npm packages"
(cd "$FRONTEND" && npm install --no-fund --no-audit --loglevel=error)

# ---------------------------------------------------------------- PostgreSQL
info "Preparing PostgreSQL"
db_url="$(env_value DATABASE_URL)"
if [[ "$db_url" =~ @(localhost|127\.0\.0\.1) ]] && command -v psql >/dev/null 2>&1; then
  if pg_isready -q 2>/dev/null; then
    SUPER="${PGSUPERUSER:-postgres}"
    psql_admin() { psql -U "$SUPER" -d postgres -v ON_ERROR_STOP=1 -qAt "$@"; }
    if ! psql_admin -c 'select 1' >/dev/null 2>&1; then SUPER="$USER"; fi
    if psql_admin -c 'select 1' >/dev/null 2>&1; then
      psql_admin -c "DO \$\$ BEGIN
          IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'agricore') THEN
            CREATE ROLE agricore LOGIN PASSWORD 'agricore';
          END IF; END \$\$;"
      for db in agricore agricore_test; do
        if [[ -z "$(psql_admin -c "select 1 from pg_database where datname = '$db'")" ]]; then
          psql_admin -c "CREATE DATABASE $db OWNER agricore"
          echo "    created database $db"
        fi
      done
      echo "    role 'agricore' and databases agricore / agricore_test are ready"
    else
      warn "Could not connect as a Postgres superuser; create the role/databases manually (see README)"
    fi
  else
    warn "PostgreSQL is not running. Start it (brew services start postgresql@16) and re-run setup."
  fi
else
  echo "    DATABASE_URL is not local - skipping database creation"
fi

info "Setup complete. Next: bin/seed.sh  then  bin/start.sh"
