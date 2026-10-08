#!/usr/bin/env bash
# Step 5 - build the React app against the Lambda URL and publish it to CloudFront.
# Re-run this any time you change frontend code.
set -euo pipefail
source "$(dirname "$0")/_aws.sh"
require FUNCTION_URL "Run bin/aws/4-backend.sh first"
require SITE_BUCKET "Run bin/aws/2-storage.sh first"

info "Building frontend with VITE_API_URL=${FUNCTION_URL}/api"
(cd "$FRONTEND" && VITE_API_URL="${FUNCTION_URL}/api" npm run build --silent)

info "Uploading to s3://$SITE_BUCKET"
# Hashed files in assets/ never change -> cache for a year. index.html must always be fresh.
aws s3 sync "$FRONTEND/dist" "s3://$SITE_BUCKET" --delete --exclude index.html \
  --cache-control "public,max-age=31536000,immutable" --only-show-errors
aws s3 cp "$FRONTEND/dist/index.html" "s3://$SITE_BUCKET/index.html" \
  --cache-control "no-cache" --content-type "text/html" --only-show-errors

info "Clearing the CloudFront cache"
aws cloudfront create-invalidation --distribution-id "$DIST_ID" --paths "/*" --query Invalidation.Id --output text >/dev/null

STATUS="$(aws cloudfront get-distribution --id "$DIST_ID" --query Distribution.Status --output text)"
echo
echo "${c_bold}AgriCore is live:${c_off}  https://$CLOUDFRONT_DOMAIN"
[[ "$STATUS" == "Deployed" ]] || echo "    (CloudFront status: $STATUS - the URL starts working when it says Deployed)"
