#!/usr/bin/env bash
# Shared helpers for the AWS deployment scripts. Sourced, not run directly.
#
# Every value a script creates (endpoints, passwords, IDs) is saved to
# .aws-deploy.env at the repo root, so later steps can read it. That file
# holds secrets and is git-ignored - never commit it.
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/_common.sh"

APP="agricore"
export AWS_REGION="${AWS_REGION:-us-east-1}"
export AWS_DEFAULT_REGION="$AWS_REGION"
export AWS_PAGER=""                    # stop the CLI opening "less" for output
STATE="$ROOT/.aws-deploy.env"

# Load saved state if it exists
[[ -f "$STATE" ]] && source "$STATE"

save() {  # save KEY VALUE -> appends/replaces a line in .aws-deploy.env
  local key="$1" value="$2"
  touch "$STATE"; chmod 600 "$STATE"
  grep -v "^${key}=" "$STATE" > "$STATE.tmp" || true
  printf "%s=%q\n" "$key" "$value" >> "$STATE.tmp"
  mv "$STATE.tmp" "$STATE"
  export "$key=$value"
}

require() {  # require VAR "message if missing"
  [[ -n "${!1:-}" ]] || die "$2"
}

command -v aws >/dev/null || die "AWS CLI not found - install it: brew install awscli"
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text 2>/dev/null)" \
  || die "AWS credentials not working. Run: aws sso login  (or aws configure), then: export AWS_PROFILE=<name>"

info "AWS account $ACCOUNT_ID  ·  region $AWS_REGION  ·  profile ${AWS_PROFILE:-default}"
