#!/usr/bin/env bash
# Step 3 - load the demo data into RDS and the report files into the real S3 bucket.
# Runs the same bin/seed.sh you use locally, just pointed at AWS.
set -euo pipefail
source "$(dirname "$0")/_aws.sh"
require DATABASE_URL_AWS "Run bin/aws/1-database.sh first"
require DOCS_BUCKET "Run bin/aws/2-storage.sh first"

info "Seeding RDS ($DB_HOST) and s3://$DOCS_BUCKET"
# Override the local .env: real bucket, no emulator endpoint, no fake keys.
# boto3 then uses your AWS_PROFILE credentials.
export S3_BUCKET="$DOCS_BUCKET" S3_ENDPOINT_URL=""
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY
"$ROOT/bin/seed.sh" --database-url "$DATABASE_URL_AWS" --yes
echo "    Next: bin/aws/4-backend.sh"
