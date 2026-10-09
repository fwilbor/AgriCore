# AgriCore on AWS: Deployment Demo Talk (5–7 minutes)

**Live app:** https://d1i8l6cuhztitq.cloudfront.net
**API:** https://asbiuncrvsvmott2e4ry5ru3qq0hqqsr.lambda-url.us-east-1.on.aws

The talk has three proof points, each one something the audience can *see* rather than take on trust:
1. **It's really in the cloud:** the browser's Network tab shows every call going to AWS Lambda.
2. **The files really are private:** a signed S3 link opens the PDF, and the same link with the signature deleted gets **Access Denied**.
3. **It's really built on these services:** `bin/aws/status.sh` shows each AWS piece live from the terminal, including the file you uploaded seconds earlier.

> **Don't open the Lambda page in the AWS Console on screen.** Its Configuration tab shows `DATABASE_URL` with the database password. `status.sh` shows the same facts with the secrets hidden.

---

## 30 minutes before

```bash
cd ~/ACT-GROUP17/agricore
export AWS_PROFILE=Franklin
bin/aws/3-seed.sh        # fresh demo data: 56 units, 7 low fuel, 2 flagged
```

- [ ] **Warm up the Lambda:** open https://d1i8l6cuhztitq.cloudfront.net, log in as admin, click Dashboard, then sign out. That avoids a 1–3 s cold start in front of the audience.
- [ ] **Run `bin/aws/status.sh` once** to make sure it prints cleanly. If it says "credentials not working", check that `export AWS_PROFILE=Franklin` is set in *that* terminal.
- [ ] **Browser:** one clean window at 125% zoom, on the login page. Press **F12** (or Cmd+Option+I), open the **Network** tab, click the **Fetch/XHR** filter, and dock DevTools at the bottom.
- [ ] **Terminal:** font enlarged (Cmd + `+`), `clear`ed, `AWS_PROFILE` set, in the `agricore` folder.
- [ ] **VS Code:** `docs/DEPLOY_AWS.md` open in Markdown preview (Cmd+Shift+V), scrolled to the diagram in section 1.
- [ ] `docs/demo-assets/hydraulic-inspection.pdf` ready in Finder.
- [ ] **Backup:** `bin/start.sh` works locally, in case the venue Wi-Fi fails.

---

## The talk (target 6:00)

### 0:00–0:40 · Hook: it's live
**On screen:** the browser at the CloudFront URL, with the padlock visible.

> "AgriCore isn't running on my laptop. It's live on AWS at this CloudFront address, over HTTPS. In the next six minutes I'll show you where each piece runs, how the pieces are locked down, and how one set of scripts deploys the whole thing."

### 0:40–1:40 · Architecture: same code, different environment
**On screen:** VS Code, with the diagram in `DEPLOY_AWS.md`.

Point along the diagram from left to right:
> "Four AWS services, each replacing something I ran locally.
> - The **React app** is static files in a private **S3** bucket, served worldwide by **CloudFront**.
> - The **FastAPI** backend runs on **AWS Lambda**. The one line `handler = Mangum(app)` adapts it, and a **Function URL** gives it a public HTTPS address.
> - The data lives in **RDS PostgreSQL**.
> - Service reports go to a second, **private S3 bucket** through boto3.
>
> The key design point: **I didn't change application code to deploy.** The same Python runs locally and in Lambda. Only environment variables differ: the database URL, the bucket name, the allowed origin."

### 1:40–2:50 · Proof 1: the browser talks to Lambda
**On screen:** the browser, with DevTools Network open.

1. **Click "Farm Operations Admin"** on the login page.
2. In the Network list, **click the `login` request** → *Headers*:
   > "The Request URL is `…lambda-url.us-east-1.on.aws/api/auth/login`. That's AWS Lambda. The response holds the signed JWT that every other call sends back."
3. **Click the `summary` request** → scroll to the *Response Headers*:
   > "`access-control-allow-origin: https://d1i8l6cuhztitq.cloudfront.net`. FastAPI's CORS settings allow browser calls from **only** my CloudFront domain. A copy of this page on another site would be refused."
4. Point at the dashboard numbers: "56 units, 7 low on fuel, 2 farms flagged. That's PostgreSQL in RDS answering the five business questions."
5. **Click Equipment, then press Cmd+R to refresh.**
   > "Refreshing a deep link works. S3 has no file called `/equipment`, so CloudFront is set to answer 403 and 404 errors with `index.html`, and React Router takes it from there."

### 2:50–4:10 · Proof 2: private files, temporary links (the highlight)
1. **Sign out → "Farm Hand".** Then **Field Jobs**, search `VLVP-2022-0018`, **⋮ → Start** on job #82.
2. **📎 → choose `hydraulic-inspection.pdf` → Upload to S3.**
   > "That file went from the browser to Lambda, and Lambda used boto3 to put it into a private S3 bucket. PostgreSQL stores only its `s3://` address."
3. **Click the open icon.** The branded PDF opens in a new tab. **Click the address bar** and point:
   > "This isn't a public link. It's a **presigned URL**: `X-Amz-Expires=300` means it dies in five minutes, and `X-Amz-Signature` proves Lambda authorised it."
4. **Delete everything from the `?` onwards → Enter.** The page shows **AccessDenied**.
   > "The same file without the signature is denied. The bucket is fully private; the only way in is a short-lived link the API issues after checking your login and role."

*(Pause here and let it land. This is the most convincing moment of the talk.)*

### 4:10–5:40 · Proof 3: the infrastructure, live
**On screen:** the terminal.
```bash
bin/aws/status.sh
```
Walk down the five sections, about 15 seconds each:
1. **CloudFront:** "Deployed, HTTP redirects to HTTPS, and there's the 403/404 → `index.html` rule from a minute ago."
2. **Lambda:** "Handler `app.main.handler` is my Mangum line. Python 3.12, 1 GB of memory, running **inside my VPC**. The environment variable *names* are listed but their values are hidden. Secrets never belong on a screen."
3. **IAM role:** "**Least privilege.** The Lambda can read, write and delete objects in *one* bucket. No other bucket, no database admin, no IAM. Even if the code were compromised, the damage is contained."
4. **RDS:** "PostgreSQL on a small instance. Its firewall admits exactly two sources: the **Lambda's security group** and my laptop's IP, which I used for seeding. I reference a security group because Lambda has no fixed IP address."
5. **S3 documents:** "Public access blocked, and here's the newest upload: the hydraulic inspection PDF from a moment ago. The browser, Lambda, IAM and S3 all lined up."
6. **Logs:** "These are CloudWatch records of my requests. Most ran in **under 50 milliseconds**, and Lambda bills by the millisecond, so a demo day costs fractions of a cent."

### 5:40–6:20 · Automation and cost
**On screen:** the VS Code file explorer with `bin/aws/` expanded.
> "The whole stack deploys with five scripts:
> 1. the database and its firewall rules
> 2. the buckets and CloudFront
> 3. the seed data
> 4. the backend
> 5. the frontend
>
> Every script is safe to re-run. Change backend code and step 4 rebuilds and redeploys it in about a minute. One detail I'm proud of: the Lambda needs **Linux** builds of compiled libraries like psycopg and bcrypt, and the script downloads those even though I'm on a Mac, with no Docker required.
>
> It costs about fifteen dollars a month, nearly all of it the database, and `teardown.sh` removes everything with one command."

### 6:20–6:50 · Close
> "To recap: CloudFront and S3 for the frontend, Lambda through Mangum for the API, RDS for the data, and a private S3 bucket with presigned links for documents. It's least-privilege IAM throughout, and the code didn't change. For production, I'd move the secrets into **Secrets Manager**, define the infrastructure in **CDK or Terraform**, and redeploy on every merge with **GitHub Actions**. Thank you. Happy to take questions."

---

## 5-minute cut
Skip the architecture diagram; say its two sentences over the live app instead. In `status.sh`, cover only Lambda, IAM and S3. Keep both browser proofs in full.

---

## If something goes wrong

| Problem | What to do (keep narrating calmly) |
| --- | --- |
| The first click is slow (2–3 s) | "That's a Lambda **cold start**: AWS spinning up a fresh copy of my API. The next calls take milliseconds." That's a teaching moment, not a failure. |
| The PDF link says "Request has expired" | The presigned URL passed 5 minutes. Click the open icon again for a fresh one. That actually proves expiry. |
| `status.sh` says credentials aren't working | Wrong terminal. `export AWS_PROFILE=Franklin`, then run it again. |
| Venue Wi-Fi is down | Switch to a phone hotspot. If that fails too, run `bin/start.sh` locally and show the same clicks: "identical code, running locally." |
| Report count shows more than 76 | Uploads from rehearsals stay in S3 after a reseed. That's harmless; ignore it. |

---

## Likely questions, with answers

**Why Lambda instead of EC2 or containers?** There's no server to patch, it scales automatically from zero to thousands of requests, and it bills per millisecond. That suits a cooperative tool with bursty daytime use. The trade-off is cold starts.

**What's a cold start, and how would you reduce it?** When no warm copy of the function exists, AWS loads the code first, which takes 1–3 s. You can reduce it with more memory (already 1 GB), a smaller package, or *provisioned concurrency* to keep copies warm.

**Why a Function URL rather than API Gateway?** The API needs only one HTTPS endpoint, and FastAPI already handles routing, auth and CORS. API Gateway adds throttling, API keys and usage plans, which would be the next step at scale.

**How does Lambda reach the database securely?** The Lambda runs inside the VPC with its own security group, and the database's security group allows port 5432 from that group only. Traffic is encrypted with `sslmode=require`.

**How does a Lambda inside a VPC reach S3?** Through an **S3 gateway endpoint**, a free private route. The alternative, a NAT gateway, costs about $32 a month.

**Where are the secrets?** In the Lambda's environment variables, set by the deploy script and never in Git. The production upgrade is AWS Secrets Manager with automatic rotation.

**Is the data encrypted?**
- **In transit, yes:** HTTPS through CloudFront and the Function URL, and TLS to the database.
- **At rest on S3, yes:** AES-256 on both buckets.
- **At rest on this RDS instance, no:** I missed that flag on the first deploy. The script now sets `--storage-encrypted` for new databases. AWS can't turn encryption on in place, so for this one I'd snapshot it, copy the snapshot with encryption, and restore. It's a good lesson in checking defaults.

**Why is the database publicly accessible?** So I could seed it from my laptop. The firewall allows only my single IP and the Lambda. In production it would be private, with seeding through a bastion host or AWS Systems Manager.

**What happens under heavy load?** Lambda scales out automatically. The bottleneck becomes database connections, because each Lambda copy opens its own. **RDS Proxy** pools them.

**Why CloudFront in front of S3?** HTTPS, caching at edge locations close to users, and a private bucket. Through **Origin Access Control**, only CloudFront can read the files.

**How do you deploy an update?** Run `bin/aws/4-backend.sh` for API changes or `5-frontend.sh` for UI changes. Each takes about a minute. The next step is running those from GitHub Actions after the tests pass.

**What does it cost?** About $15 a month, mostly the database. Lambda, S3 and CloudFront cost pennies at this scale.
