<p align="center">
  <img src="frontend/public/brand/agricore-logo.jpg" alt="AgriCore - Equipment. Service. Insight." width="280">
</p>

# AgriCore — Smart Farm Command Center

A full-stack command center for **Prairie Crest Agricultural Cooperative**. It tracks shared heavy equipment, field jobs, and service reports across member farms. Analytics answer the cooperative's key operational questions.

| Tier | Technology |
| --- | --- |
| Frontend | React 19 (Vite) + Material UI 7 + MUI X DataGrid 8, React Context for auth |
| Backend | Python 3.10+ · FastAPI · Pydantic v2 · JWT (PyJWT + bcrypt) |
| Database | PostgreSQL 16 · SQLAlchemy 2.0 |
| Storage | AWS S3 via `boto3`. Runs locally against a **moto** S3 emulator. |
| Lambda-ready | `app.main.handler` wraps the API with **Mangum** for AWS Lambda |

```
Browser ──► React + MUI (Vite :5173)
              │  fetch("/api/...")  + Authorization: Bearer <JWT>
              ▼
           FastAPI (:8000) ── Depends(get_current_user / require_roles) ── RBAC
              │                                   │
              ▼ SQLAlchemy Session                ▼ boto3
           PostgreSQL (:5432)                  S3 bucket (moto :5001 locally)
```

---

## Quick start

Prerequisites: **Python 3.10–3.13**, **Node 20+**, **PostgreSQL 14+** running locally (`brew services start postgresql@16`).

```bash
bin/setup.sh     # venv + pip install, npm install, .env files, Postgres role + databases
bin/seed.sh      # drop/create tables, load deterministic mock data, upload report files to S3
bin/start.sh     # S3 emulator + API + frontend.  Ctrl+C stops everything.
```

Then open **http://localhost:5173**. The API's interactive docs are at **http://localhost:8000/docs**.

| Role | Email | Password |
| --- | --- | --- |
| Farm Operations Admin | `admin@prairiecrest.coop` | `AgriCore2026!` |
| Farm Hand (Tyler Hansen) | `farmhand@prairiecrest.coop` | `AgriCore2026!` |
| Auditor (read-only) | `auditor@prairiecrest.coop` | `AgriCore2026!` |

The login page also has one-click demo buttons for each role.

### Helper scripts (`bin/`)

| Script | Purpose |
| --- | --- |
| `setup.sh` | Picks Python ≥ 3.10 and creates `backend/.venv`. Installs `requirements.txt` and npm packages. Writes `backend/.env` with a random JWT secret, plus `frontend/.env`. Creates the `agricore` Postgres role and the `agricore` and `agricore_test` databases. Safe to re-run. |
| `seed.sh` | Recreates all tables and seeds 6 farms, 56 equipment units, 239 field jobs, 76 service reports and 17 users. A fixed random seed makes the numbers identical on every run. Options: `--yes` (no prompt), `--database-url URL` (e.g. RDS), `--files-only` (re-upload report files only). |
| `start.sh` | Starts the S3 emulator, restores seeded report files, and runs `uvicorn --reload` on :8000 and Vite on :5173. |
| `test.sh` | Runs the backend pytest suite (26 tests) and a production frontend build. |

---

## Project layout

```
agricore/
├── backend/
│   ├── app/
│   │   ├── main.py          FastAPI app, CORS, router wiring, Mangum Lambda handler
│   │   ├── config.py        typed settings from env / .env (pydantic-settings)
│   │   ├── database.py      SQLAlchemy engine, SessionLocal, get_db dependency
│   │   ├── models.py        ORM tables: User, Farm, Equipment, FieldJob, ServiceReport, AuditLog
│   │   ├── schemas.py       Pydantic v2 request/response models + validation rules
│   │   ├── enums.py         Role, EquipmentStatus, JobStatus, JobPriority, EquipmentType
│   │   ├── security.py      bcrypt hashing, JWT create/decode
│   │   ├── deps.py          get_current_user, require_roles(...) → RBAC
│   │   ├── storage.py       boto3 S3 upload, presigned download URLs
│   │   ├── audit.py         audit-log helper
│   │   ├── seed.py          deterministic mock data
│   │   └── routers/         auth, users, farms, equipment, jobs, reports, analytics, audit_logs
│   ├── tests/               pytest: auth/RBAC, CRUD/validation, S3 uploads, analytics
│   └── requirements.txt
├── frontend/src/
│   ├── api/client.js        fetch wrapper (JWT header, error messages, 401 → logout)
│   ├── context/             AuthContext (session state), NotifyContext (toasts)
│   ├── components/          Layout, AppDataGrid, FormDialog, ReportsDialog, chips, cards
│   ├── pages/               Login, Dashboard, Equipment, Jobs, Farms, Users, AuditLog
│   └── hooks.js             useApi() data-fetching hook
├── frontend/public/brand/   web-sized logo, wordmark, mascot badge, favicons
├── assets/                  master logo artwork (source for everything in brand/)
├── bin/                     setup.sh, seed.sh, start.sh, test.sh
└── docs/
    ├── LEARNING_GUIDE.md    how Python + this stack fit together (study this)
    ├── DEMO_SCRIPT.md       timed 5–8 minute demo script + prep checklist + Q&A
    └── analytics.sql        the five business questions in raw SQL
```

---

## Data model

```
Farm 1───* Equipment 1───* FieldJob 1───* ServiceReport
  │            │               │
  │ supervisor │ assigned_to   │ operator
  ▼            ▼               ▼
 User ◄─── supervisor_id ── User (farm hand, farm_id = home farm)
```

Additions beyond the brief, and why:

* `Equipment.assigned_to_id`: the co-location question needs to know which farmhand a unit is assigned to.
* `User.farm_id`: a farmhand's home farm. Also needed for co-location.
* `User.supervisor_id`: models the reporting lines to Regional Agronomy Supervisors.
* `AuditLog`: lets the Auditor role "search system logs".
* `ServiceReport.file_key`: the S3 object key. Kept next to `file_url` (`s3://bucket/key`) so the API can create presigned URLs and delete files.

Definitions used by the analytics:

* **Active equipment** = status `Idle` or `In-Use`. Maintenance and Retired units are excluded.
* **Active job** = `Pending` or `In-Progress`.
* The maintenance percentage excludes `Retired` units from a farm's fleet size.

---

## RBAC matrix

| Capability | Admin | Farm Hand | Auditor |
| --- | :-: | :-: | :-: |
| Create / edit / delete farms, equipment, jobs, users | ✅ | ❌ 403 | ❌ 403 |
| View equipment | all | assigned to them or on their jobs | all |
| View field jobs | all | their own (others → 404) | all |
| Change job status (`PATCH /jobs/{id}/status`) | ✅ | own, unfinished jobs | ❌ |
| Upload service reports to S3 | ✅ | own jobs | ❌ |
| Analytics dashboard, users list, audit log | ✅ | ❌ 403 | ✅ |

The rules are enforced in the API through FastAPI dependencies in `backend/app/deps.py`. The UI hides controls only for convenience.

---

## API reference

All routes are prefixed with `/api`. They need `Authorization: Bearer <token>` except login and health. Full interactive docs are at `/docs`.

| Method | Path | Roles | Notes |
| --- | --- | --- | --- |
| POST | `/auth/login` | public | form fields `username`, `password` → `{access_token, user}` |
| GET | `/auth/me` | any | current user |
| GET | `/health` | public | liveness |
| GET / POST | `/users` | read: admin, auditor · write: admin | `?role=farm_hand` |
| PATCH / DELETE | `/users/{id}` | admin | DELETE = deactivate (soft delete) |
| GET / POST | `/farms` | read: any · write: admin | |
| GET / PATCH / DELETE | `/farms/{id}` | read: any · write: admin | 409 if the farm still has equipment |
| GET / POST | `/equipment` | read: any (scoped) · write: admin | `?status=&equipment_type=&facility_id=&search=` |
| GET / PATCH / DELETE | `/equipment/{id}` | read: any (scoped) · write: admin | 409 when deleting a unit with job history (retire it instead) |
| GET / POST | `/jobs` | read: any (scoped) · write: admin | `?status=&priority=&equipment_id=` |
| GET / PATCH / DELETE | `/jobs/{id}` | read: any (scoped) · write: admin | |
| PATCH | `/jobs/{id}/status` | admin, farm hand | `{status}`. Keeps the equipment status in sync. |
| GET / POST | `/jobs/{id}/reports` | read: any (scoped) · upload: admin, farm hand | multipart `file` + `notes`. png/jpg/webp/txt/pdf up to 10 MB. |
| GET | `/reports` | admin, auditor | all reports |
| GET | `/reports/{id}/download-url` | any (scoped) | presigned S3 URL, valid 5 minutes |
| DELETE | `/reports/{id}` | admin | also deletes the S3 object |
| GET | `/analytics/low-fuel?threshold=20` | admin, auditor | Q1 |
| GET | `/analytics/co-location` | admin, auditor | Q2 |
| GET | `/analytics/reliability` | admin, auditor | Q3 |
| GET | `/analytics/maintenance-flags?threshold=0.3&only_flagged=false` | admin, auditor | Q4 |
| GET | `/analytics/supervisor-activity?supervisor_id=` | admin, auditor | Q5 |
| GET | `/analytics/summary` | admin, auditor | dashboard metric cards |
| GET | `/audit-logs?search=&action=` | admin, auditor | |

Status codes in use: `200`, `201` (created), `204` (deleted), `401` (no or invalid token), `403` (wrong role), `404`, `409` (business-rule conflict), `413`, `415` (file checks), `422` (Pydantic validation).

---

## Testing

```bash
bin/test.sh            # pytest + frontend build
cd backend && .venv/bin/pytest -k analytics -v   # just the analytics tests
```

The tests use a separate `agricore_test` database, so your demo data is never touched. They replace S3 with moto's in-process mock.

---

## Deploying to AWS

The full walkthrough is in **[docs/DEPLOY_AWS.md](docs/DEPLOY_AWS.md)**. In short, with `AWS_PROFILE` set:

```bash
bin/aws/1-database.sh   # RDS PostgreSQL + security groups
bin/aws/2-storage.sh    # private docs bucket, site bucket, CloudFront (OAC)
bin/aws/3-seed.sh       # same seed data, loaded into RDS + real S3
bin/aws/4-backend.sh    # Linux package -> Lambda (handler app.main.handler) + Function URL
bin/aws/5-frontend.sh   # build with VITE_API_URL, upload, invalidate -> https://<id>.cloudfront.net
bin/aws/teardown.sh     # delete everything afterwards (about $15/month if left running)
```

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `role "agricore" does not exist` | Start Postgres, then re-run `bin/setup.sh` |
| Postgres won't start after a crash or reboot (`lock file "postmaster.pid" already exists`) | Make sure no `postgres` process is running (`ps aux \| grep postgres`), then delete `/usr/local/var/postgresql@16/postmaster.pid` and run `brew services restart postgresql@16` |
| `Port 8000 is busy` | `lsof -i :8000`, then stop that process |
| App loads but shows no data; nothing answers on port 8000 | The API crashed at startup, usually because Postgres was still starting after a reboot. Save any backend file (or `touch backend/app/main.py`) to make it reload, or press Ctrl+C and re-run `bin/start.sh`, which now waits for Postgres. |
| Opening a service report gives 404 | The S3 emulator was restarted. `bin/start.sh` re-uploads the files, or run `bin/seed.sh --files-only` |
| Logged out unexpectedly | The JWT expired (8 hours). Sign in again. |
