# AgriCore Demo Script (5–8 minutes)

The script follows the showcase rubric: **RBAC walkthrough → Data grid and dashboard → Code architecture tour.** The data is deterministic, so every number below is what you'll see after `bin/seed.sh`.

> **About "Live Cloud URL" (rubric item 1).** This build runs locally, which we chose deliberately. Say it up front, in one sentence, and frame it as deployment-ready (see the opening below). If your instructor scores item 1 strictly, confirm with them beforehand. The README's "Deploying to AWS" section lists the exact steps.

---

## Before you present

### 2–3 days before
- [ ] Read `LEARNING_GUIDE.md` Parts 1–4, and do at least exercises 2, 3 and 6.
- [ ] Run the full script below **3 times out loud with a timer**. Aim for 7:00, so you have a minute of slack.
- [ ] Practise the code tour with the files already open in VS Code tabs, in the order listed.

### The day before
- [ ] `bin/test.sh` shows 26 passing tests and a successful build. Take a screenshot as a fallback.
- [ ] Do a full dry run on the **same laptop, screen and resolution** you'll present on.

### 30 minutes before
```bash
brew services start postgresql@16      # if it isn't running
bin/seed.sh --yes                      # resets all data to the known numbers
bin/start.sh                           # leave this terminal running
```
- [ ] **Browser:** a clean window (no bookmarks bar), zoom **110–125%**, and close other tabs. Open:
  1. `http://localhost:5173/login`
  2. `http://localhost:8000/docs` (Swagger, as a backup or bonus)
- [ ] **VS Code:** open these tabs in this order, zoomed in (Cmd + `+`):
  1. `backend/app/schemas.py` (scroll to `class EquipmentBase`)
  2. `backend/app/deps.py`
  3. `backend/app/database.py`
  4. `backend/app/routers/analytics.py` (scroll to `query_maintenance`)
  5. `backend/app/storage.py`
  6. `frontend/src/context/AuthContext.jsx`
- [ ] Have `docs/demo-assets/hydraulic-inspection.pdf` handy in Finder for the upload. It's an AgriCore-branded inspection report for the exact pump in the story (VLVP-2022-0018, 18% fuel), so when it opens from S3 the audience sees your logo.
- [ ] Load the login page once before presenting. The first load after a code change can trigger a one-time Vite reload.
- [ ] Turn on Do Not Disturb, close Slack and Mail, and plug in power.

---

## The script (target 7:00)

### 0:00–0:40 · Opening (problem → solution)
**On screen:** the login page, with the AgriCore logo and the three pillars. Start talking before you click anything.

> "Prairie Crest Cooperative shares tractors, combines, sprayers and pumps across six member farms. Today that's tracked on paper and spreadsheets, so leadership can't answer basic questions: what's low on fuel, which farms are overloaded with repairs, which models keep failing.
>
> This is AgriCore. The tagline, *Equipment. Service. Insight.*, is also the shape of this demo: managing the **equipment** pool, running **service** work in the field, and the **insight** leadership was missing. Under the hood it's React and Material UI on the front, FastAPI with Pydantic v2 in Python, PostgreSQL through SQLAlchemy 2.0, and S3 for service reports through boto3. I'm running it locally today. The backend already has its Lambda entry point through Mangum, and S3 runs against an emulator, so the same boto3 code points at real AWS by changing one environment variable."

### 0:40–2:30 · Admin: the analytics dashboard (answers all 5 business questions)
**Click:** "Farm Operations Admin" demo login.

> "I'm logged in as Jordan, the Operations Admin. Each panel answers one of the cooperative's five questions, and each is a single SQL aggregation in PostgreSQL, not a Python loop."

Point at each panel and say one sentence:

1. **Metric cards:** "56 units across 6 farms, 14 in maintenance, a 79.6% job completion rate."
2. **Low Fuel Alert (7):** "Seven active units under 20%." **Click 30%:** "The threshold is a query parameter, validated by Pydantic between 0 and 100." **Click back to 20%.**
3. **Maintenance Flags:** "Golden Hollow is at 40% and Willow Creek at 37.5%, both flagged. Bluestem is at 28.6%, just under. That query uses a SQL HAVING clause."
4. **Reliability by Model:** "The Claas Lexion combine completes only 54% of its jobs. 13 of 28 failed. That's a purchasing conversation."
5. **Reporting Lines:** **Change the dropdown to Maria Gonzalez.** "Three of her four farmhands have active jobs. One doesn't, so there's spare capacity."
6. **Co-location (scroll down):** "Five units are assigned to a farmhand based at a different farm. For example, Tyler Hansen at Prairie Crest North holds a pump at Willow Creek. Remember Tyler."

### 2:30–3:40 · Admin: data grid, CRUD and validation
**Click:** Equipment.

> "This is the MUI DataGrid: sortable columns, pagination, and live search."

- **Type** `lexion` in the search box → 7 rows. **Clear it.**
- **Click** the "Maintenance (14)" chip, then click "All".
- **Click** the "Fuel" header to sort.
- **Click "Add equipment":** serial `demo-0001`, model `Demo Tractor`, type Tractor, any farm. **Select the existing 100 in the fuel box and replace it with 150**, then **Save.**
  > "The server rejected this, not the browser. Pydantic says fuel must be ≤ 100, and that 422 error is shown right here."
- **Change fuel to `80` → Save.** "Created. Pydantic also upper-cased the serial number with a field validator."

### 3:40–5:00 · Farm Hand: restricted role, job status, S3 upload
**Click:** Sign out → "Farm Hand".

> "Now I'm Tyler, a farm hand. The nav is smaller: no Users, no Audit Log, no analytics. He sees only his 10 units and his own jobs. That filtering happens in the API with a WHERE clause, not just in the UI."

- **Click** Field Jobs. Find **job #82, "Pump flow test – Home Place", VLVP-2022-0018**. That's the low-fuel, off-site pump from the dashboard. Click the **⋮** menu → **Start (In-Progress)**.
  > "Starting a job also flips the machine to In-Use. That's a business rule in the API."
- **Click the 📎 paperclip** → **Choose file** → `hydraulic-inspection.pdf` → notes "Seal replaced, pressure test passed" → **Upload to S3**.
  > "FastAPI received the file, checked the type and size, and boto3 uploaded it to a private S3 bucket. PostgreSQL stores the s3:// URL you see here."
- **Click the open-in-new icon:** the PDF opens in a new tab.
  > "The bucket is private. The API generated a presigned URL that works for five minutes."
- Close the tab and the dialog.

### 5:00–5:30 · Auditor: read-only
**Click:** Sign out → "Auditor".

- **Click** Equipment: "No Add, Edit or Delete buttons. If someone forced the request anyway, the API returns 403."
- **Click** Audit Log → type `UPLOAD` in the search box. "Here's Tyler's upload from a minute ago. Every login, change, status update and upload is recorded."

### 5:30–7:20 · Code architecture tour (switch to VS Code)
Spend about 20 seconds per file. **Show; don't read the code aloud.**

1. **`schemas.py`, `EquipmentBase`.**
   > "Pydantic v2 models are the API's contract. `Field(ge=0, le=100)` is the rule that rejected 150. The validator upper-cases serials. Separate Create, Update and Out models mean the password hash can never appear in a response."
2. **`deps.py`.**
   > "This is the security chain built from FastAPI dependencies. `get_current_user` decodes the JWT, giving 401 if it's bad. `require_roles` is a factory that returns a checker, giving 403 if the role is wrong. Endpoints declare their permission in the signature: `admin: AdminUser`."
3. **`database.py`, `get_db`.**
   > "One SQLAlchemy session per request. The yield hands it to the endpoint, and finally always closes it, even on errors."
4. **`analytics.py`, `query_maintenance`.**
   > "SQLAlchemy 2.0 Core: COUNT with FILTER, a LEFT JOIN to keep empty farms, NULLIF against divide-by-zero, and HAVING for the over-30% filter. Postgres does the math."
5. **`storage.py`.**
   > "boto3 `upload_fileobj` with server-side encryption, and `generate_presigned_url` for downloads. Locally the endpoint is moto. In AWS you delete one variable."
6. **`AuthContext.jsx`.**
   > "On the front end, the React Context API holds the session: user, token, login, logout and a hasRole helper. Any component calls `useAuth()`, so there's no prop drilling. A 401 from any request logs you out automatically."

### 7:20–7:45 · Close
> "**Equipment. Service. Insight.** To recap: three roles enforced in the API, five business questions answered by SQL aggregations, a validated REST API, and S3 document storage. There are 26 automated tests covering RBAC, validation, uploads and the analytics numbers. Setup is three scripts: setup, seed, start. Thank you. Happy to take questions."

---

## The 5-minute cut (if you're running long)
Keep: opening (0:30), dashboard (1:15, skip the toggle), the equipment search plus the validation error (0:45), the farm-hand upload (1:00), and the code tour with only `schemas.py`, `deps.py` and `analytics.py` (1:15). Skip the auditor section, but say one line about it: "the Auditor sees the same screens read-only."

---

## If something breaks mid-demo

| Problem | Recovery (stay calm, narrate it) |
| --- | --- |
| Page shows no data / network error | Check the `bin/start.sh` terminal. Run `curl localhost:8000/api/health`. Restart `bin/start.sh`. |
| PDF link gives 404 | The S3 emulator restarted. "Files live in an in-memory emulator locally." Run `bin/seed.sh --files-only`. |
| Login fails | The data was wiped. Run `bin/seed.sh --yes` (5 seconds). |
| Anything else | Switch to Swagger at `/docs`: click **Authorize**, then run `GET /api/analytics/summary`. Same story, different view. |
| Total failure | Show the screenshots in `docs/screenshots/` and walk the code tour. Code is half the rubric. |

---

## Likely questions, with short answers

**Why FastAPI over Flask or Django?** Type hints drive validation, serialisation and the auto-generated Swagger docs. Dependency injection makes auth reusable. It's async-capable and runs on Lambda through Mangum.

**What does Pydantic do that you'd otherwise hand-write?** Parsing, type coercion, range and regex checks, enum checks, and a precise 422 error showing which field failed and why. It also filters responses so internal fields can't leak.

**How does `Depends` work?** FastAPI inspects the endpoint's parameters. For each `Depends(fn)` it calls `fn` first, recursively resolving that function's own dependencies, and passes in the result. Generator dependencies like `get_db` get cleanup code after `yield`.

**401 vs 403?** 401: no valid identity (missing, bad or expired token). 403: valid identity, wrong role.

**Why 404 instead of 403 for another farmhand's job?** It doesn't reveal that the record exists. That's a common security practice.

**Is the JWT secure if anyone can read it?** Reading it is fine. It holds no secrets, only the user id, role and expiry. Tampering breaks the HMAC signature, which only the server can produce with `JWT_SECRET`. It expires after 8 hours.

**Why store the token in localStorage?** It's simple and survives a refresh. The trade-off is exposure to XSS. In production I'd use an httpOnly cookie, or keep localStorage with a strict Content-Security-Policy.

**How are passwords stored?** bcrypt hashes with a per-password salt. They're never stored or returned in plain text.

**Why do the analytics in SQL instead of Python?** The database is built for aggregation. One query returns 6 rows instead of pulling thousands of rows into Python, and it scales with indexes.

**What's `HAVING` vs `WHERE`?** `WHERE` filters rows before grouping. `HAVING` filters groups after aggregation. "Farms over 30% in maintenance" is a property of the group.

**What counts as "active equipment"?** Idle or In-Use. Units in maintenance or retired can't be fuelled up and dispatched, so they're excluded.

**Why can't I delete equipment?** It has job history, and deleting it would distort the reliability metrics. The API returns 409 and tells you to retire it instead.

**How would you deploy this?** RDS for Postgres, a private S3 bucket, the backend on Lambda (handler `app.main.handler`) behind a Function URL, and the frontend build on S3 + CloudFront with `VITE_API_URL` set. The README lists the steps. Configuration is all environment variables.

**How do you know the numbers are right?** `docs/analytics.sql` has the same five questions in raw SQL, and `tests/test_analytics.py` asserts the exact answers on seeded data.

**What would you add next?** Alembic migrations instead of `create_all`, server-side DataGrid pagination for large fleets, refresh tokens, real-time telemetry ingestion for fuel levels, and charts for trends over time.
