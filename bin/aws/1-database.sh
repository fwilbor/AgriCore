#!/usr/bin/env bash
# Step 1 - RDS PostgreSQL
#   * security group for Lambda (outbound only)
#   * security group for the database: port 5432 open to the Lambda group + your laptop's IP
#   * a db.t4g.micro PostgreSQL instance with a generated password
# Takes 5-10 minutes (AWS is building a server for you).
set -euo pipefail
source "$(dirname "$0")/_aws.sh"

VPC_ID="$(aws ec2 describe-vpcs --filters Name=is-default,Values=true --query 'Vpcs[0].VpcId' --output text)"
[[ "$VPC_ID" != "None" ]] || die "No default VPC in $AWS_REGION. Create one: aws ec2 create-default-vpc"
save VPC_ID "$VPC_ID"

sg_id() { aws ec2 describe-security-groups --filters Name=vpc-id,Values="$VPC_ID" Name=group-name,Values="$1" \
            --query 'SecurityGroups[0].GroupId' --output text; }

LAMBDA_SG="$(sg_id ${APP}-lambda-sg)"
if [[ "$LAMBDA_SG" == "None" ]]; then
  info "Creating security group ${APP}-lambda-sg"
  LAMBDA_SG="$(aws ec2 create-security-group --group-name ${APP}-lambda-sg --vpc-id "$VPC_ID" \
                --description "AgriCore Lambda function" --query GroupId --output text)"
fi
save LAMBDA_SG "$LAMBDA_SG"

DB_SG="$(sg_id ${APP}-db-sg)"
if [[ "$DB_SG" == "None" ]]; then
  info "Creating security group ${APP}-db-sg"
  DB_SG="$(aws ec2 create-security-group --group-name ${APP}-db-sg --vpc-id "$VPC_ID" \
            --description "AgriCore PostgreSQL" --query GroupId --output text)"
  aws ec2 authorize-security-group-ingress --group-id "$DB_SG" --protocol tcp --port 5432 \
    --source-group "$LAMBDA_SG" >/dev/null
fi
save DB_SG "$DB_SG"

MY_IP="$(curl -s https://checkip.amazonaws.com | tr -d '[:space:]')"
info "Allowing your IP ($MY_IP) to reach the database for seeding"
aws ec2 authorize-security-group-ingress --group-id "$DB_SG" --protocol tcp --port 5432 \
  --cidr "${MY_IP}/32" >/dev/null 2>&1 || echo "    (rule already exists)"

DB_ID="${APP}-db"
if ! aws rds describe-db-instances --db-instance-identifier "$DB_ID" >/dev/null 2>&1; then
  if [[ -z "${DB_PASSWORD:-}" ]]; then
    save DB_PASSWORD "$("$VENV/bin/python" -c 'import secrets,string; a=string.ascii_letters+string.digits; print("".join(secrets.choice(a) for _ in range(28)))')"
  fi
  info "Creating RDS PostgreSQL instance $DB_ID (db.t4g.micro, 20 GB)"
  aws rds create-db-instance \
    --db-instance-identifier "$DB_ID" \
    --engine postgres \
    --db-instance-class db.t4g.micro \
    --allocated-storage 20 --storage-type gp3 \
    --master-username agricore --master-user-password "$DB_PASSWORD" \
    --db-name agricore \
    --vpc-security-group-ids "$DB_SG" \
    --publicly-accessible \
    --backup-retention-period 1 \
    --no-multi-az --no-deletion-protection \
    --tags Key=project,Value=$APP >/dev/null
fi

info "Waiting for the database to become available (5-10 minutes)..."
aws rds wait db-instance-available --db-instance-identifier "$DB_ID"
DB_HOST="$(aws rds describe-db-instances --db-instance-identifier "$DB_ID" \
            --query 'DBInstances[0].Endpoint.Address' --output text)"
save DB_HOST "$DB_HOST"
save DATABASE_URL_AWS "postgresql+psycopg://agricore:${DB_PASSWORD}@${DB_HOST}:5432/agricore?sslmode=require"

info "Database ready: $DB_HOST"
echo "    Next: bin/aws/2-storage.sh"
