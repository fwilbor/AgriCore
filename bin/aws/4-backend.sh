#!/usr/bin/env bash
# Step 4 - FastAPI on AWS Lambda
#   * builds a Linux-compatible zip of backend/app + its dependencies (no Docker needed)
#   * IAM role: logs, VPC networking, and read/write on the documents bucket only
#   * S3 gateway endpoint so the Lambda (inside the VPC) can reach S3 for free
#   * creates or updates the function, then exposes it with a public Function URL
# Re-run this any time you change backend code - it updates in place.
set -euo pipefail
source "$(dirname "$0")/_aws.sh"
require DATABASE_URL_AWS "Run bin/aws/1-database.sh first"
require DOCS_BUCKET "Run bin/aws/2-storage.sh first"
require CLOUDFRONT_DOMAIN "Run bin/aws/2-storage.sh first"

FN="${APP}-api"
ROLE="${APP}-lambda-role"
BUILD="$ROOT/.run/lambda"

# ------------------------------------------------------------------ 1. package
info "Building the Lambda package (Linux wheels for Python 3.12)"
rm -rf "$BUILD"; mkdir -p "$BUILD/package"
# --platform/--only-binary download wheels compiled for Amazon Linux, not macOS.
"$VENV/bin/pip" install --quiet --upgrade \
  --platform manylinux2014_x86_64 --implementation cp --python-version 3.12 --only-binary=:all: \
  --target "$BUILD/package" -r "$BACKEND/requirements-lambda.txt"
cp -R "$BACKEND/app" "$BUILD/package/app"
find "$BUILD/package" -name "__pycache__" -type d -prune -exec rm -rf {} +
(cd "$BUILD/package" && zip -q -r "$BUILD/function.zip" .)
echo "    package size: $(du -h "$BUILD/function.zip" | cut -f1)"

# ------------------------------------------------------------------ 2. IAM role
if ! aws iam get-role --role-name "$ROLE" >/dev/null 2>&1; then
  info "Creating IAM role $ROLE"
  aws iam create-role --role-name "$ROLE" --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{ "Effect": "Allow", "Principal": { "Service": "lambda.amazonaws.com" }, "Action": "sts:AssumeRole" }]
  }' >/dev/null
  aws iam attach-role-policy --role-name "$ROLE" --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
  aws iam attach-role-policy --role-name "$ROLE" --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole
  NEW_ROLE=1
fi
# Least privilege: this function may only touch objects in the documents bucket.
aws iam put-role-policy --role-name "$ROLE" --policy-name "${APP}-docs-bucket" --policy-document "{
  \"Version\": \"2012-10-17\",
  \"Statement\": [
    { \"Effect\": \"Allow\", \"Action\": [\"s3:PutObject\", \"s3:GetObject\", \"s3:DeleteObject\"],
      \"Resource\": \"arn:aws:s3:::${DOCS_BUCKET}/*\" },
    { \"Effect\": \"Allow\", \"Action\": \"s3:ListBucket\", \"Resource\": \"arn:aws:s3:::${DOCS_BUCKET}\" }
  ]
}"
ROLE_ARN="$(aws iam get-role --role-name "$ROLE" --query Role.Arn --output text)"
if [[ -n "${NEW_ROLE:-}" ]]; then echo "    waiting 15s for the new role to propagate..."; sleep 15; fi

# ------------------------------------------------------------------ 3. networking
SUBNETS="$(aws ec2 describe-subnets --filters Name=vpc-id,Values="$VPC_ID" Name=default-for-az,Values=true \
            --query 'Subnets[].SubnetId' --output text | tr '\t' ',')"
ROUTE_TABLES="$(aws ec2 describe-route-tables --filters Name=vpc-id,Values="$VPC_ID" \
                 --query 'RouteTables[].RouteTableId' --output text)"
S3_ENDPOINT_ID="$(aws ec2 describe-vpc-endpoints --filters Name=vpc-id,Values="$VPC_ID" \
                   Name=service-name,Values="com.amazonaws.${AWS_REGION}.s3" \
                   --query 'VpcEndpoints[0].VpcEndpointId' --output text)"
if [[ "$S3_ENDPOINT_ID" == "None" ]]; then
  info "Creating S3 gateway endpoint (lets the in-VPC Lambda reach S3; free)"
  # shellcheck disable=SC2086
  S3_ENDPOINT_ID="$(aws ec2 create-vpc-endpoint --vpc-id "$VPC_ID" --vpc-endpoint-type Gateway \
    --service-name "com.amazonaws.${AWS_REGION}.s3" --route-table-ids $ROUTE_TABLES \
    --query VpcEndpoint.VpcEndpointId --output text)"
fi
save S3_ENDPOINT_ID "$S3_ENDPOINT_ID"

# ------------------------------------------------------------------ 4. environment
[[ -n "${JWT_SECRET_AWS:-}" ]] || save JWT_SECRET_AWS "$("$VENV/bin/python" -c 'import secrets; print(secrets.token_urlsafe(48))')"
ENV_FILE="$BUILD/env.json"
DATABASE_URL_AWS="$DATABASE_URL_AWS" JWT_SECRET_AWS="$JWT_SECRET_AWS" DOCS_BUCKET="$DOCS_BUCKET" \
CLOUDFRONT_DOMAIN="$CLOUDFRONT_DOMAIN" "$VENV/bin/python" - > "$ENV_FILE" <<'PY'
import json, os
print(json.dumps({"Variables": {
    "DATABASE_URL": os.environ["DATABASE_URL_AWS"],
    "JWT_SECRET": os.environ["JWT_SECRET_AWS"],
    "CORS_ORIGINS": json.dumps([f"https://{os.environ['CLOUDFRONT_DOMAIN']}"]),
    "S3_BUCKET": os.environ["DOCS_BUCKET"],
    "MAX_UPLOAD_MB": "4",   # Lambda request bodies are capped at 6 MB
}}))
PY

# ------------------------------------------------------------------ 5. function
if aws lambda get-function --function-name "$FN" >/dev/null 2>&1; then
  info "Updating Lambda function $FN"
  aws lambda update-function-code --function-name "$FN" --zip-file "fileb://$BUILD/function.zip" >/dev/null
  aws lambda wait function-updated-v2 --function-name "$FN"
  aws lambda update-function-configuration --function-name "$FN" --environment "file://$ENV_FILE" >/dev/null
  aws lambda wait function-updated-v2 --function-name "$FN"
else
  info "Creating Lambda function $FN"
  aws lambda create-function --function-name "$FN" \
    --runtime python3.12 --architectures x86_64 \
    --handler app.main.handler \
    --role "$ROLE_ARN" \
    --zip-file "fileb://$BUILD/function.zip" \
    --memory-size 1024 --timeout 30 \
    --vpc-config "SubnetIds=${SUBNETS},SecurityGroupIds=${LAMBDA_SG}" \
    --environment "file://$ENV_FILE" \
    --tags project=$APP >/dev/null
  echo "    waiting for the function to become active (VPC setup takes ~1 minute)..."
  aws lambda wait function-active-v2 --function-name "$FN"
fi

# ------------------------------------------------------------------ 6. Function URL
if ! aws lambda get-function-url-config --function-name "$FN" >/dev/null 2>&1; then
  info "Creating public Function URL"
  aws lambda create-function-url-config --function-name "$FN" --auth-type NONE >/dev/null
  # Public URL = anyone may call it; FastAPI's JWT checks protect the data.
  aws lambda add-permission --function-name "$FN" --statement-id public-url \
    --action lambda:InvokeFunctionUrl --principal "*" --function-url-auth-type NONE >/dev/null
  # Newer AWS accounts also require InvokeFunction, limited to calls that come through the URL.
  aws lambda add-permission --function-name "$FN" --statement-id public-url-invoke \
    --action lambda:InvokeFunction --principal "*" --invoked-via-function-url >/dev/null 2>&1 \
    || warn "Could not add the InvokeFunction permission (older CLI?). If /api/health returns 403, see docs/DEPLOY_AWS.md troubleshooting."
fi
FUNCTION_URL="$(aws lambda get-function-url-config --function-name "$FN" --query FunctionUrl --output text)"
save FUNCTION_URL "${FUNCTION_URL%/}"

info "Smoke test: ${FUNCTION_URL%/}/api/health"
sleep 3
curl -s --max-time 30 "${FUNCTION_URL%/}/api/health" || true; echo
echo "    Next: bin/aws/5-frontend.sh"
