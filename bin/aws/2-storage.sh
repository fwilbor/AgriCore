#!/usr/bin/env bash
# Step 2 - S3 buckets and CloudFront
#   * private document bucket for service reports (boto3 uploads here)
#   * private website bucket for the built React app
#   * CloudFront distribution in front of the website bucket (HTTPS + CDN),
#     allowed to read the bucket through an Origin Access Control
# CloudFront takes 5-15 minutes to roll out worldwide.
set -euo pipefail
source "$(dirname "$0")/_aws.sh"

DOCS_BUCKET="${APP}-docs-${ACCOUNT_ID}-${AWS_REGION}"
SITE_BUCKET="${APP}-site-${ACCOUNT_ID}-${AWS_REGION}"

make_private_bucket() {
  local b="$1"
  if aws s3api head-bucket --bucket "$b" 2>/dev/null; then
    echo "    bucket $b already exists"; return
  fi
  info "Creating private bucket $b"
  if [[ "$AWS_REGION" == "us-east-1" ]]; then
    aws s3api create-bucket --bucket "$b" >/dev/null
  else
    aws s3api create-bucket --bucket "$b" --create-bucket-configuration LocationConstraint="$AWS_REGION" >/dev/null
  fi
  aws s3api put-public-access-block --bucket "$b" --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
  aws s3api put-bucket-encryption --bucket "$b" --server-side-encryption-configuration \
    '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
}

make_private_bucket "$DOCS_BUCKET"; save DOCS_BUCKET "$DOCS_BUCKET"
make_private_bucket "$SITE_BUCKET"; save SITE_BUCKET "$SITE_BUCKET"

# --- Origin Access Control: lets CloudFront (and only CloudFront) read the site bucket
OAC_ID="$(aws cloudfront list-origin-access-controls \
           --query "OriginAccessControlList.Items[?Name=='${APP}-oac'].Id | [0]" --output text)"
if [[ "$OAC_ID" == "None" || -z "$OAC_ID" ]]; then
  info "Creating CloudFront Origin Access Control"
  OAC_ID="$(aws cloudfront create-origin-access-control --origin-access-control-config \
    "Name=${APP}-oac,SigningProtocol=sigv4,SigningBehavior=always,OriginAccessControlOriginType=s3" \
    --query OriginAccessControl.Id --output text)"
fi
save OAC_ID "$OAC_ID"

# --- CloudFront distribution
if [[ -z "${DIST_ID:-}" ]]; then
  info "Creating CloudFront distribution"
  CONFIG="$RUN_DIR/cloudfront.json"
  cat > "$CONFIG" <<JSON
{
  "CallerReference": "${APP}-$(date +%s)",
  "Comment": "AgriCore frontend",
  "Enabled": true,
  "DefaultRootObject": "index.html",
  "PriceClass": "PriceClass_100",
  "Origins": { "Quantity": 1, "Items": [ {
    "Id": "site-bucket",
    "DomainName": "${SITE_BUCKET}.s3.${AWS_REGION}.amazonaws.com",
    "OriginAccessControlId": "${OAC_ID}",
    "S3OriginConfig": { "OriginAccessIdentity": "" }
  } ] },
  "DefaultCacheBehavior": {
    "TargetOriginId": "site-bucket",
    "ViewerProtocolPolicy": "redirect-to-https",
    "CachePolicyId": "658327ea-f89d-4fab-a63d-7e88639e58f6",
    "Compress": true,
    "AllowedMethods": { "Quantity": 2, "Items": ["GET", "HEAD"] }
  },
  "CustomErrorResponses": { "Quantity": 2, "Items": [
    { "ErrorCode": 403, "ResponsePagePath": "/index.html", "ResponseCode": "200", "ErrorCachingMinTTL": 0 },
    { "ErrorCode": 404, "ResponsePagePath": "/index.html", "ResponseCode": "200", "ErrorCachingMinTTL": 0 }
  ] }
}
JSON
  read -r DIST_ID DIST_DOMAIN <<<"$(aws cloudfront create-distribution --distribution-config "file://$CONFIG" \
    --query 'Distribution.[Id,DomainName]' --output text)"
  save DIST_ID "$DIST_ID"
  save CLOUDFRONT_DOMAIN "$DIST_DOMAIN"
fi

# --- Bucket policy: allow this distribution to read the site bucket
info "Granting CloudFront read access to the site bucket"
POLICY="$RUN_DIR/site-bucket-policy.json"
cat > "$POLICY" <<JSON
{
  "Version": "2012-10-17",
  "Statement": [ {
    "Sid": "AllowCloudFrontRead",
    "Effect": "Allow",
    "Principal": { "Service": "cloudfront.amazonaws.com" },
    "Action": "s3:GetObject",
    "Resource": "arn:aws:s3:::${SITE_BUCKET}/*",
    "Condition": { "StringEquals": {
      "AWS:SourceArn": "arn:aws:cloudfront::${ACCOUNT_ID}:distribution/${DIST_ID}" } }
  } ]
}
JSON
aws s3api put-bucket-policy --bucket "$SITE_BUCKET" --policy "file://$POLICY"

info "Storage ready"
echo "    Documents bucket : $DOCS_BUCKET"
echo "    Website bucket   : $SITE_BUCKET"
echo "    App URL (soon)   : https://$CLOUDFRONT_DOMAIN   (CloudFront needs 5-15 min to deploy)"
echo "    Next: bin/aws/3-seed.sh"
