#!/usr/bin/env bash
# Live, read-only tour of the AgriCore deployment - built for showing on screen.
# Never prints secrets: environment variable *names* only, no values.
#
#   bin/aws/status.sh          full tour
#   bin/aws/status.sh logs     just the recent Lambda invocations (cold starts, durations)
set -euo pipefail
source "$(dirname "$0")/_aws.sh"
require FUNCTION_URL "Nothing deployed yet - run bin/aws/deploy.sh"

FN="${APP}-api"
h() { echo; echo "${c_bold}${c_green}■ $*${c_off}"; }

logs() {
  h "Lambda invocations in the last 15 minutes (CloudWatch Logs)"
  echo "   'Init Duration' = a cold start. Billed Duration = what AWS charges for."
  aws logs tail "/aws/lambda/$FN" --since 15m --format short --filter-pattern REPORT 2>/dev/null \
    | sed -E 's/RequestId: [a-f0-9-]+[[:space:]]*//; s/Memory Size: [0-9]+ MB[[:space:]]*//' | tail -8 \
    || echo "   (no requests yet - open the app first)"
}
if [[ "${1:-}" == "logs" ]]; then logs; exit 0; fi

h "1. Frontend - CloudFront + private S3 bucket"
aws cloudfront get-distribution --id "$DIST_ID" \
  --query 'Distribution.{URL:DomainName,Status:Status,HTTPS:DistributionConfig.DefaultCacheBehavior.ViewerProtocolPolicy,SpaFallback:DistributionConfig.CustomErrorResponses.Items[*].join(`→`,[to_string(ErrorCode),ResponsePagePath])}' \
  --output table
echo "   Files in $SITE_BUCKET: $(aws s3 ls "s3://$SITE_BUCKET" --recursive | wc -l | tr -d ' ')"

h "2. API - AWS Lambda running FastAPI through Mangum"
aws lambda get-function-configuration --function-name "$FN" \
  --query '{Handler:Handler,Runtime:Runtime,MemoryMB:MemorySize,TimeoutSec:Timeout,InVPC:VpcConfig.VpcId,LastDeploy:LastModified}' \
  --output table
echo "   Function URL : $FUNCTION_URL"
echo "   Env var names: $(aws lambda get-function-configuration --function-name "$FN" \
  --query 'keys(Environment.Variables)' --output text | tr '\t' ' ')   (values hidden)"
echo -n "   Health check : "; curl -s --max-time 20 -w "  (%{time_total}s)\n" "$FUNCTION_URL/api/health"

h "3. Least-privilege IAM role - what the Lambda may do in S3"
aws iam get-role-policy --role-name "${APP}-lambda-role" --policy-name "${APP}-docs-bucket" \
  --query 'PolicyDocument.Statement' --output json \
  | "$VENV/bin/python" -c '
import json, sys
for st in json.load(sys.stdin):
    acts = st["Action"] if isinstance(st["Action"], list) else [st["Action"]]
    print("   ✓ %-45s on %s" % (", ".join(acts), st["Resource"]))
print("   ✗ everything else in the account (no other bucket, no database admin, no IAM)")'


h "4. Database - RDS PostgreSQL"
aws rds describe-db-instances --db-instance-identifier "${APP}-db" \
  --query 'DBInstances[0].{Engine:join(` `,[Engine,EngineVersion]),Class:DBInstanceClass,Status:DBInstanceStatus,StorageGB:AllocatedStorage}' \
  --output table
echo "   Firewall (security group $DB_SG) - who may connect on port 5432:"
aws ec2 describe-security-groups --group-ids "$DB_SG" \
  --query 'SecurityGroups[0].IpPermissions[0].[UserIdGroupPairs[].GroupId, IpRanges[].CidrIp]' --output text \
  | tr '\t' '\n' | sed -E "s/^($LAMBDA_SG)$/   ✓ \1  (the Lambda's security group)/; s#^[0-9]+\.[0-9]+\.[0-9]+\.([0-9]+)/32\$#   ✓ •••.•••.•••.\1/32  (my laptop's IP, for seeding)#"

h "5. Documents - private S3 bucket"
echo "   Bucket       : $DOCS_BUCKET"
echo "   Report files : $(aws s3 ls "s3://$DOCS_BUCKET/service-reports/" --recursive | wc -l | tr -d ' ')"
echo -n "   Public access blocked: "
aws s3api get-public-access-block --bucket "$DOCS_BUCKET" \
  --query 'PublicAccessBlockConfiguration.RestrictPublicBuckets' --output text
echo "   Newest upload:"
aws s3api list-objects-v2 --bucket "$DOCS_BUCKET" --prefix service-reports/ \
  --query 'reverse(sort_by(Contents,&LastModified))[0].[LastModified,Key,Size]' --output text | sed 's/^/     /'

logs
echo
echo "${c_bold}Live app:${c_off} https://$CLOUDFRONT_DOMAIN"
