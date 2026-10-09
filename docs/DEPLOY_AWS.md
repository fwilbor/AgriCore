# Deploying AgriCore to AWS

This guide takes you from "runs on my laptop" to a live HTTPS URL. Five scripts in `bin/aws/` do the work. Each section explains **what** the script creates, **why** it's needed, and **where to see it** in the AWS Console, so you understand the deployment as well as run it.

**Time:** about 45 minutes, mostly waiting on AWS. **Cost:** see [Costs](#costs). Run the [teardown](#7-teardown-after-the-showcase) when you're done.

---

## 1. The big picture

Every local piece has a cloud equivalent, and the **code doesn't change**. Only environment variables do.

| Piece | On your laptop | On AWS | What switches it |
| --- | --- | --- | --- |
| Frontend | Vite dev server :5173 | **S3** bucket (files) + **CloudFront** (HTTPS + CDN) | `VITE_API_URL` at build time |
| API | `uvicorn` :8000 | **Lambda** + **Function URL**, via `handler = Mangum(app)` | the Lambda handler setting |
| Database | Homebrew Postgres | **RDS** PostgreSQL | `DATABASE_URL` |
| Documents | moto emulator :5001 | **S3** private bucket | no `S3_ENDPOINT_URL`, plus `S3_BUCKET` |
| Credentials | fake `testing` keys | **IAM role** attached to the Lambda | no keys at all |

```
                    https://dxxxx.cloudfront.net
 Browser ─────────────────► CloudFront ──(OAC)──► S3 site bucket (index.html, JS, CSS)
    │
    │ fetch https://xxxx.lambda-url.us-east-1.on.aws/api/...   (JWT in header)
    ▼
 Lambda Function URL ──► Lambda: FastAPI via Mangum ─────► RDS PostgreSQL
                           │   (inside the VPC)        SG rule: only the Lambda's SG
                           │
                           └──(S3 gateway endpoint)──► S3 docs bucket (private)
                                                         ▲
 Browser ◄──── presigned URL (5 min) ───────────────────┘
```

### Concepts you'll meet

| Term | Plain-English meaning | Where it shows up |
| --- | --- | --- |
| **Region** | Which AWS data centre (we use `us-east-1`) | every command |
| **VPC** | Your private network inside AWS. Every account has a *default VPC*. | RDS and Lambda live in it |
| **Security group (SG)** | A firewall attached to a resource. It lists who may connect in. | `agricore-db-sg` lets in only the Lambda and your IP |
| **IAM role** | An identity that an AWS service assumes, with a policy listing allowed actions | `agricore-lambda-role` may read and write only the docs bucket |
| **Lambda** | Runs your code on demand. No server to manage; you pay per request. | `agricore-api` |
| **Function URL** | A built-in HTTPS address for a Lambda. It replaces API Gateway for simple cases. | the API's public URL |
| **Cold start** | The first request after idle takes 1–3 s while Lambda loads your code | first page load |
| **CloudFront** | A CDN: copies your static files to edge locations worldwide and serves them over HTTPS | the app URL |
| **OAC** | Origin Access Control: lets CloudFront, and only CloudFront, read a private bucket | site bucket policy |
| **Gateway endpoint** | A free private route from the VPC to S3, so the Lambda reaches S3 without internet access | `vpce-...` |
| **Presigned URL** | A temporary signed link to one private S3 object | opening service reports |

---

## 2. Before you start

1. **Pick the AWS profile** to deploy with. You have several configured:
   ```bash
   aws configure list-profiles
   export AWS_PROFILE=<the profile for this project>
   aws sso login              # only if it's an SSO profile
   aws sts get-caller-identity
   ```
   The last command should print your account ID. **Every script uses whatever `AWS_PROFILE` is set in that terminal**, so run all the steps in the same terminal window.
2. **Region:** the scripts default to `us-east-1`. To use another, run `export AWS_REGION=us-east-2` first.
3. **Local setup already done:** you've run `bin/setup.sh` before, so `backend/.venv` exists. The scripts reuse its Python and pip.
4. **Permissions:** your profile needs rights to create RDS, S3, CloudFront, Lambda, IAM roles and EC2 security groups. An admin or "AdministratorAccess" profile works.

> **Secrets file:** the scripts save generated values (the database password, JWT secret and URLs) to `.aws-deploy.env` at the repo root. It's git-ignored. **Never commit it, and never paste it into chat or slides.**

---

## 3. Step by step

Run each script on its own the first time, so you can watch what it does. (`bin/aws/deploy.sh` runs all five in a row once you're comfortable.)

### Step 1: Database (RDS)
```bash
bin/aws/1-database.sh
```
**What it creates**
- `agricore-lambda-sg`: a security group for the Lambda. It allows no inbound traffic, because nothing connects *to* the Lambda through the network; requests arrive through the Function URL.
- `agricore-db-sg`: a security group for the database. Port 5432 is open to **only two sources**: anything wearing `agricore-lambda-sg`, and your current public IP, so you can seed from your laptop.
- `agricore-db`: a PostgreSQL instance (`db.t4g.micro`, 20 GB gp3). The master user is `agricore`, the password is a random 28-character string, and the initial database is `agricore`.

**Why it's built this way:** the database is reachable from the internet in principle, but the security group admits only your Lambda and your own IP. Referencing a *security group* instead of an IP address matters because Lambda doesn't have fixed IPs.

**What you'll see:** "Waiting for the database..." for 5–10 minutes. Then it saves `DATABASE_URL_AWS` (with `sslmode=require`, so traffic is encrypted).

**Look in the Console:** RDS → Databases → `agricore-db`. Check the endpoint, the security group, and that "Publicly accessible" is Yes. Then EC2 → Security Groups → `agricore-db-sg` → Inbound rules.

### Step 2: Storage and CDN (S3 + CloudFront)
```bash
bin/aws/2-storage.sh
```
**What it creates**
- `agricore-docs-<account>-<region>`: the private bucket for service reports. Public access is blocked and encryption is on. Bucket names must be globally unique, which is why the account ID is in the name.
- `agricore-site-<account>-<region>`: a private bucket for the built React files.
- An **Origin Access Control** and a **CloudFront distribution**:
  - HTTPS only: HTTP redirects to HTTPS.
  - `index.html` is the default page.
  - **403 and 404 errors are answered with `/index.html`.** This matters: React Router handles URLs like `/equipment` in the browser, but S3 has no file by that name. Without this rule, refreshing any page except `/` would show an error.
- A **bucket policy** on the site bucket allowing exactly this distribution to read it.

**What you'll see:** the CloudFront domain, e.g. `d1a2b3c4.cloudfront.net`. It takes 5–15 minutes to deploy worldwide. Carry on meanwhile.

**Look in the Console:** CloudFront → your distribution → *Error pages* tab and *Origins* tab. S3 → site bucket → *Permissions* → Bucket policy.

### Step 3: Seed the cloud database
```bash
bin/aws/3-seed.sh
```
This is the **same `bin/seed.sh`** you use locally, with three overrides:
- `--database-url` points at RDS.
- `S3_BUCKET` is the real docs bucket.
- `S3_ENDPOINT_URL` is empty, so boto3 talks to real S3 using **your profile's** credentials.

You get the same deterministic data, so **every number in `DEMO_SCRIPT.md` still holds**: 56 units, 7 low fuel, 2 flagged farms. The 76 seeded report files are uploaded to the real bucket.

**Look in the Console:** S3 → docs bucket → `service-reports/` folder. Open one object and notice that you can't download it publicly. That's the private bucket working.

### Step 4: Backend (Lambda)
```bash
bin/aws/4-backend.sh
```
**What it does, in order**
1. **Builds the package.** `pip install --platform manylinux2014_x86_64 --python-version 3.12 --only-binary=:all:` downloads **Linux** builds of the compiled libraries (psycopg, pydantic-core, bcrypt). Your Mac's own builds would crash on Lambda. It copies `backend/app/` alongside them and zips the result to about 14 MB. It uses `backend/requirements-lambda.txt`, which leaves out uvicorn, moto and pytest. boto3 is already included in Lambda's Python runtime.
2. **Creates the IAM role `agricore-lambda-role`:**
   - `AWSLambdaBasicExecutionRole`: write logs to CloudWatch.
   - `AWSLambdaVPCAccessExecutionRole`: join the VPC to reach RDS.
   - An inline policy allowing Get, Put and Delete on **only** `agricore-docs-…/*`. This is *least privilege*: even if the code were compromised, it couldn't touch any other bucket.
3. **Creates the S3 gateway endpoint.** A Lambda inside a VPC has no internet access, and that includes S3. The gateway endpoint adds a free private route to S3. The alternative, a NAT gateway, costs about $32 a month.
4. **Sets the environment variables:**

   | Variable | Value |
   | --- | --- |
   | `DATABASE_URL` | the RDS URL |
   | `JWT_SECRET` | a new random secret, separate from your local one |
   | `CORS_ORIGINS` | `["https://<cloudfront domain>"]`, so only your frontend's origin may call the API from a browser |
   | `S3_BUCKET` | the docs bucket |
   | `MAX_UPLOAD_MB` | `4`, because Lambda caps request bodies at 6 MB |

5. **Creates the function `agricore-api`:**
   - Runtime Python 3.12, 1024 MB of memory, 30 s timeout.
   - Handler **`app.main.handler`**, which is the `Mangum(app)` line at the bottom of `main.py`.
   - Placed in the default VPC's subnets with `agricore-lambda-sg`.
6. **Creates the Function URL** with auth type `NONE`, so it's publicly reachable. FastAPI's JWT checks still protect every endpoint except login and health.
7. **Smoke test:** runs `curl <function-url>/api/health` and expects `{"status":"ok"}`.

**Look in the Console:**
- Lambda → `agricore-api`:
  - *Configuration → Environment variables*. Note how a secret like `DATABASE_URL` is visible here; that's one reason production setups use Secrets Manager.
  - *Configuration → Function URL*.
  - *Monitor → View CloudWatch logs*, which shows the same log lines uvicorn prints locally.

### Step 5: Frontend
```bash
bin/aws/5-frontend.sh
```
1. Runs `VITE_API_URL=https://<function-url>/api npm run build`. Vite bakes that URL into the JavaScript, which is the only frontend change.
2. Uploads `dist/` to the site bucket:
   - `assets/*` files have content hashes in their names, so they're cached for a year.
   - `index.html` is set to `no-cache`, so a new deploy shows up immediately.
3. Invalidates the CloudFront cache.
4. Prints **`https://<id>.cloudfront.net`**, your live app URL.

---

## 4. Check it end to end

Open the CloudFront URL, then:
- [ ] **Login page:** your logo shows and the browser shows a padlock (HTTPS).
- [ ] **Admin:** the dashboard shows 56 units, 7 low fuel, 2 flagged, 5 co-location issues and a 79.6% completion rate.
- [ ] **Equipment:** searching `lexion` gives 7 rows, and fuel = 150 gives the Pydantic error.
- [ ] **Farm Hand:** start job #82, upload `docs/demo-assets/hydraulic-inspection.pdf`, and open it. The address bar shows an `amazonaws.com` presigned URL.
- [ ] **Auditor:** the audit log search `UPLOAD` shows that upload.
- [ ] **Refresh on `/equipment`:** it still works (this checks the 403/404 → index.html rule).
- [ ] **API docs:** `https://<function-url>/docs` opens Swagger, served by Lambda.

---

## 5. Updating after code changes

| You changed | Run |
| --- | --- |
| Backend Python | `bin/aws/4-backend.sh` (rebuilds and updates the function in place) |
| Frontend React | `bin/aws/5-frontend.sh` |
| Want fresh demo data | `bin/aws/3-seed.sh` |
| Your IP changed (new Wi-Fi) and seeding can't connect | `bin/aws/1-database.sh` (adds your new IP and leaves the rest alone) |

All the scripts are **safe to re-run**: they check what already exists.

---

## 6. Using the cloud URL in the showcase

The full timed talk for presenting the deployment is in **[DEPLOY_DEMO_SCRIPT.md](DEPLOY_DEMO_SCRIPT.md)**. For a secret-free live tour of the infrastructure from the terminal, run `bin/aws/status.sh`.

- Update the opening line in `DEMO_SCRIPT.md` from "I'm running it locally" to: *"This is live on AWS. CloudFront serves the React app, the API runs on Lambda through Mangum, the data is in RDS PostgreSQL, and service reports go to a private S3 bucket."*
- **Warm it up 5 minutes before you present.** Open the URL and log in once, so the Lambda isn't cold when the audience is watching.
- **Keep the local setup ready as a backup** (`bin/start.sh`). Venue Wi-Fi is the most common demo failure.
- **Reseed before you present:** `bin/aws/3-seed.sh`, so the numbers match the script.
- Bonus talking point: show the Lambda's CloudWatch logs while you click through the app.

---

## 7. Teardown (after the showcase)

```bash
bin/aws/teardown.sh
```
It asks you to type `delete agricore`, then removes the Lambda, the IAM role, RDS (with no final snapshot), both buckets and all their files, CloudFront, the VPC endpoint and the security groups. CloudFront and RDS take 10–20 minutes to delete; the script waits.

Afterwards, check the RDS, CloudFront and S3 consoles to confirm nothing is left. **RDS is the only item that costs real money while idle.**

---

## Costs

Rough monthly costs if left running, in us-east-1:

| Service | Cost |
| --- | --- |
| RDS `db.t4g.micro` + 20 GB storage | about $14/month. Free-tier eligibility depends on your account's age and plan, so check the Billing console. |
| Lambda, S3, CloudFront, gateway endpoint | pennies at demo traffic. The gateway endpoint is free. |
| **Total** | **about $15/month**, or about $0.50 per day |

To be safe, create a budget alert: Billing → Budgets → *Create budget* → a $10 monthly cost budget with an email alert.

---

## Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| `AWS credentials not working` | The SSO session expired. Run `aws sso login` and check that `AWS_PROFILE` is set in *this* terminal. |
| Step 3 hangs or times out connecting to RDS | Your IP changed, or the database isn't ready yet. Re-run `1-database.sh`. Some networks (corporate or campus) block port 5432; try a phone hotspot. |
| `/api/health` returns `{"Message":"Forbidden"}` | The Function URL permission is missing. In Lambda → Configuration → Function URL → Edit, set Auth type to **NONE** and save; the console adds both permissions. |
| `/api/health` times out (30 s) | The Lambda can't reach RDS. Check that `agricore-db-sg` has an inbound rule from `agricore-lambda-sg`. Look in CloudWatch logs for `connection timeout`. |
| Browser console: `CORS policy … No 'Access-Control-Allow-Origin'` | `CORS_ORIGINS` doesn't exactly match the CloudFront URL (`https://`, no trailing slash). Re-run `4-backend.sh`. |
| The app loads but every call fails with network errors | The frontend was built against the wrong API URL. Re-run `5-frontend.sh`. |
| Refreshing `/jobs` shows an XML "AccessDenied" page | The CloudFront error-page rule is missing. Check CloudFront → Error pages: 403 and 404 should map to `/index.html` with a 200 response. |
| Opening a report gives 403 from S3 | The Lambda role lacks `s3:GetObject` on the docs bucket. Re-run `4-backend.sh`, which re-applies the policy. |
| Upload fails for large files | The Lambda request limit is 6 MB, and the app caps uploads at 4 MB. Production apps upload *directly* to S3 with a presigned **PUT** URL instead. |
| The first request is slow (2–3 s) | A cold start. Warm the app up before demoing. Raising memory (already 1024 MB) helps cold starts too. |

---

## What a production setup would add

These are good answers if a judge asks "what would you change for production?":
- **Secrets Manager** for `DATABASE_URL` and `JWT_SECRET`, instead of plain environment variables.
- **RDS not publicly accessible**, seeding through a bastion host or a one-off Lambda, and **RDS Proxy** to pool connections from many concurrent Lambdas.
- **Infrastructure as code** (AWS CDK, Terraform or AWS SAM) instead of shell scripts, so the whole stack is versioned and repeatable.
- **CI/CD** (GitHub Actions) that runs the tests and then `4-backend.sh` and `5-frontend.sh` on every merge.
- **Custom domain** with an ACM certificate (e.g. `agricore.prairiecrest.coop`), and serving `/api/*` through the same CloudFront distribution so CORS isn't needed.
- **Direct-to-S3 uploads** with presigned PUT URLs, so files never pass through Lambda's 6 MB limit.
- **Alembic migrations** instead of `create_all`.
