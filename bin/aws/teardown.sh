#!/usr/bin/env bash
# Delete everything the deploy scripts created, so nothing keeps billing.
# RDS deletion skips the final snapshot - the demo data can be re-seeded anytime.
set -euo pipefail
source "$(dirname "$0")/_aws.sh"

warn "This permanently deletes the AgriCore Lambda, RDS database, S3 buckets (and files) and CloudFront distribution in $AWS_REGION."
read -r -p "Type 'delete agricore' to continue: " answer
[[ "$answer" == "delete agricore" ]] || die "Aborted"

FN="${APP}-api"; ROLE="${APP}-lambda-role"

info "Lambda"
aws lambda delete-function-url-config --function-name "$FN" 2>/dev/null || true
aws lambda delete-function --function-name "$FN" 2>/dev/null || true

info "IAM role"
aws iam delete-role-policy --role-name "$ROLE" --policy-name "${APP}-docs-bucket" 2>/dev/null || true
for arn in arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole; do
  aws iam detach-role-policy --role-name "$ROLE" --policy-arn "$arn" 2>/dev/null || true
done
aws iam delete-role --role-name "$ROLE" 2>/dev/null || true

info "RDS (deleting in the background)"
aws rds delete-db-instance --db-instance-identifier "${APP}-db" --skip-final-snapshot --delete-automated-backups >/dev/null 2>&1 || true

info "S3 buckets"
for b in "${DOCS_BUCKET:-}" "${SITE_BUCKET:-}"; do
  [[ -n "$b" ]] || continue
  aws s3 rb "s3://$b" --force >/dev/null 2>&1 || true
done

if [[ -n "${DIST_ID:-}" ]]; then
  info "CloudFront: disabling (must finish before it can be deleted, ~10-15 min)"
  ETAG="$(aws cloudfront get-distribution-config --id "$DIST_ID" --query ETag --output text 2>/dev/null || true)"
  if [[ -n "$ETAG" ]]; then
    aws cloudfront get-distribution-config --id "$DIST_ID" --query DistributionConfig --output json > "$RUN_DIR/cf-config.json"
    "$VENV/bin/python" -c "import json,sys; p=sys.argv[1]; c=json.load(open(p)); c['Enabled']=False; json.dump(c,open(p,'w'))" "$RUN_DIR/cf-config.json"
    aws cloudfront update-distribution --id "$DIST_ID" --if-match "$ETAG" --distribution-config "file://$RUN_DIR/cf-config.json" >/dev/null
    aws cloudfront wait distribution-deployed --id "$DIST_ID"
    ETAG="$(aws cloudfront get-distribution-config --id "$DIST_ID" --query ETag --output text)"
    aws cloudfront delete-distribution --id "$DIST_ID" --if-match "$ETAG"
  fi
  [[ -n "${OAC_ID:-}" ]] && { OETAG="$(aws cloudfront get-origin-access-control --id "$OAC_ID" --query ETag --output text 2>/dev/null)" \
    && aws cloudfront delete-origin-access-control --id "$OAC_ID" --if-match "$OETAG" 2>/dev/null || true; }
fi

info "Waiting for RDS to finish deleting, then removing network pieces"
aws rds wait db-instance-deleted --db-instance-identifier "${APP}-db" 2>/dev/null || true
[[ -n "${S3_ENDPOINT_ID:-}" ]] && aws ec2 delete-vpc-endpoints --vpc-endpoint-ids "$S3_ENDPOINT_ID" >/dev/null 2>&1 || true
# Lambda's network interfaces can linger for a few minutes after the function is deleted.
for sg in "${DB_SG:-}" "${LAMBDA_SG:-}"; do
  [[ -n "$sg" ]] || continue
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    aws ec2 delete-security-group --group-id "$sg" 2>/dev/null && break
    sleep 30
  done
done

mv "$STATE" "$STATE.deleted-$(date +%Y%m%d%H%M)"
info "Teardown complete. (Saved values moved to $(basename "$STATE").deleted-*)"
