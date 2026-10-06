# AgriCore Learning Guide: Python and the stack, through this codebase

This guide teaches the stack by walking through code you'll present. Work through it with the files open next to it. Every concept points at a real line in the project.

**Suggested pace:** Day 1 covers Parts 1–3, Day 2 covers Parts 4–6, Day 3 covers Part 7, the exercises, and rehearsal (see `DEMO_SCRIPT.md`).

---

## Part 1: The big picture (read this first)

### One request, end to end

Follow what happens when a Farm Hand marks a job **Completed**:

```
1. React        JobsPage.jsx   changeStatus(row, 'Completed')
2. API client   client.js      fetch PATCH /api/jobs/82/status
                               headers: Authorization: Bearer eyJhbGciOi...
                               body:    {"status": "Completed"}
3. Vite proxy   vite.config.js forwards /api/* to http://localhost:8000
4. FastAPI      jobs.py        @router.patch("/{job_id}/status") matches the URL
5. Depends      deps.py        get_db()          -> opens a database Session
                               get_current_user  -> decodes JWT, loads User row  (401 if bad)
                               require_roles(ADMIN, FARM_HAND)                  (403 if wrong role)
6. Pydantic     schemas.py     FieldJobStatusUpdate validates the body           (422 if bad)
7. Logic        jobs.py        is it their job? (404) already finished? (409)
                               job.status = ...; sync_equipment_status(...)
                               audit.record(...)
8. SQLAlchemy   db.commit()    -> UPDATE field_jobs ...; UPDATE equipment ...; INSERT INTO audit_logs ...
9. Response     response_model=FieldJobOut turns the ORM object into JSON
10. React       notify('Job #82 → Completed'); reload() refetches the grid
```

If you can explain these 10 steps, you can answer most questions about the architecture.

### Who does what

| Layer | Its one job | Files |
| --- | --- | --- |
| **React + MUI** | Draw the screen and react to clicks | `frontend/src/pages/*` |
| **Context** | Hold global state (who's logged in) | `frontend/src/context/AuthContext.jsx` |
| **FastAPI** | Map URLs to Python functions | `backend/app/routers/*` |
| **Pydantic** | Check data coming in, shape data going out | `backend/app/schemas.py` |
| **Depends** | Run shared prerequisites (DB session, auth, roles) | `backend/app/deps.py` |
| **SQLAlchemy** | Turn Python objects into SQL and back | `backend/app/models.py`, `database.py` |
| **PostgreSQL** | Store the data and run aggregations | (the database) |
| **boto3 / S3** | Store files | `backend/app/storage.py` |

---

## Part 2: Python fundamentals, as this project uses them

You don't need all of Python to present this project. You need the parts below, and each one is used in the code.

### 2.1 Modules, packages, imports

A **module** is a `.py` file. A **package** is a folder with `__init__.py`. `backend/app/` is a package, and so is `app/routers/`.

```python
from .config import get_settings          # "." = same package (app/)
from ..deps import CurrentUser            # ".." = parent package (from app/routers/ up to app/)
from sqlalchemy import select             # third-party library installed by pip
```

Run the app as a package from `backend/`: `uvicorn app.main:app` means "in module `app/main.py`, use the variable `app`".

### 2.2 Variables, types, and type hints

Python is dynamically typed, but this codebase adds **type hints** everywhere. FastAPI and Pydantic *read* them at runtime to validate data.

```python
def get_or_404(db: Session, model: type[T], obj_id: int) -> T: ...
farm_id: int | None = None      # "an int, or None", meaning optional
items: list[LowFuelItem]
equipment_by_status: dict[str, int]
```

`X | None` is the modern way to write `Optional[X]`, and needs Python 3.10+. That's one reason the spec says "Python 3.10+".

### 2.3 Functions, default values, `*args`, `**kwargs`

```python
def require_roles(*allowed: Role):          # *allowed collects any number of positional args into a tuple
    ...
require_roles(Role.ADMIN, Role.AUDITOR)     # allowed == (Role.ADMIN, Role.AUDITOR)

Equipment(**payload.model_dump())           # ** unpacks a dict into keyword arguments:
# Equipment(serial_number="JD8R-...", model="...", fuel_level=88.5, ...)
```

### 2.4 Classes, inheritance, mixins

```python
class TimestampMixin:                        # a small reusable piece
    created_at: Mapped[datetime] = ...

class Farm(TimestampMixin, Base): ...        # Farm gets created_at + everything Base provides
```

The schemas use inheritance to avoid repetition. `EquipmentOut(EquipmentBase, ORMModel)` reuses every field from `EquipmentBase`, adds `id` and `farm_name`, and picks up `from_attributes=True` from `ORMModel`.

### 2.5 Decorators (the `@` lines)

A decorator wraps or registers a function. You'll see five kinds here:

| Decorator | What it does | Where |
| --- | --- | --- |
| `@router.get("/path")` | Registers the function as an API endpoint | every router |
| `@property` | Lets a method be read like an attribute: `equipment.farm_name` | `models.py` |
| `@field_validator("serial_number")` | A custom Pydantic validation step | `schemas.py:109` |
| `@lru_cache` | Remembers the result, so `.env` is parsed once | `config.py`, `storage.py` |
| `@asynccontextmanager` | Turns a generator into a `with`-style setup/teardown | `main.py:23` |

### 2.6 Enums

```python
class EquipmentStatus(str, Enum):
    IN_USE = "In-Use"
```

Each member *is* a string, so it compares equal to `"In-Use"` and serialises to JSON cleanly. The same enum drives the database column type (Postgres `ENUM`), Pydantic validation (`"Spaceship"` → 422), and Swagger's dropdown.

### 2.7 Generators and `yield` (very important for FastAPI)

```python
def get_db():
    db = SessionLocal()
    try:
        yield db          # pause here and hand db to the endpoint
    finally:
        db.close()        # resume after the response is sent, even if there was an error
```

A function with `yield` is a **generator**. FastAPI runs the code before `yield`, injects the value, runs your endpoint, then runs the code after `yield`. That gives you **one session per request, always closed**, with no leaks.

### 2.8 Context managers (`with`)

```python
with SessionLocal() as db:      # seed.py: the session is closed automatically at the end of the block
    seed(db)
```

`lifespan` in `main.py` is the same idea for the whole app: it creates tables and the S3 bucket on startup.

### 2.9 Closures and factories

`require_roles` *returns a function*. The inner `checker` "remembers" `allowed`:

```python
def require_roles(*allowed):
    def checker(user: CurrentUser) -> User:
        if user.role not in allowed:        # 'allowed' captured from the outer call
            raise HTTPException(403, ...)
        return user
    return checker
```

`AdminUser = Annotated[User, Depends(require_roles(Role.ADMIN))]` builds a checker once and reuses it in every admin endpoint.

### 2.10 Exceptions

`raise HTTPException(status.HTTP_409_CONFLICT, "...")` stops the endpoint immediately. FastAPI turns it into a JSON error response: `{"detail": "..."}`. In `deps.py`, `try/except jwt.PyJWTError` catches a bad token and raises 401 instead.

### 2.11 Comprehensions, f-strings, dicts

```python
[LowFuelItem(**row._mapping) for row in db.execute(stmt)]         # list comprehension
{s.value: counts.get(s, 0) for s in EquipmentStatus}              # dict comprehension
f"service-reports/job-{job_id}/{uuid.uuid4().hex[:12]}-{safe}"    # f-string
```

### 2.12 Virtual environments and pip

`backend/.venv` is a private copy of Python with this project's packages, so they don't clash with other projects. `bin/setup.sh` creates it. To use it by hand:

```bash
source backend/.venv/bin/activate     # your prompt shows (.venv)
python -c "import fastapi; print(fastapi.__version__)"
deactivate
```

---

## Part 3: Backend, file by file (the order to read them)

### 3.1 `config.py`: settings
`Settings(BaseSettings)` reads environment variables, then `backend/.env`. Every value is typed. **Why it matters for AWS:** the same code runs locally and on Lambda. Only the environment variables change.

### 3.2 `database.py`: engine, session, `get_db`
* **Engine** = the connection pool to Postgres. Created once.
* **SessionLocal** = a factory for **Sessions**. A Session is a unit of work: you add or modify objects, then `commit()` writes them in one transaction.
* `get_db` = the dependency that gives each request its own Session (see 2.7).

### 3.3 `models.py`: SQLAlchemy 2.0 ORM
```python
class Equipment(TimestampMixin, Base):
    __tablename__ = "equipment"
    id: Mapped[int] = mapped_column(primary_key=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("farms.id"))
    farm: Mapped["Farm"] = relationship(back_populates="equipment")
```
* `Mapped[...]` plus `mapped_column` is **SQLAlchemy 2.0 style**. Say "typed declarative mapping" if asked.
* `ForeignKey` is the database link. `relationship` is the Python shortcut, so you can write `equipment.farm.name`.
* `@property farm_name` exists so Pydantic can output a flat `"farm_name"` for the grid.
* `use_alter=True` on `Farm.supervisor_id` handles the fact that farms → users and users → farms reference each other.

### 3.4 `schemas.py`: Pydantic v2 (a demo talking point)
Four shapes per entity: **Base / Create / Update / Out**.
```python
class EquipmentBase(BaseModel):
    serial_number: str = Field(pattern=SERIAL_PATTERN)
    fuel_level: float = Field(ge=0, le=100)          # ge = greater-or-equal, le = less-or-equal
    equipment_type: EquipmentType                     # must be one of the enum values

    @field_validator("serial_number", mode="before")  # runs before the pattern check
    @classmethod
    def normalise_serial(cls, v): return _clean_serial(v)   # "jd8r-1" -> "JD8R-1"
```
* **Create** = what clients must send. **Update** = all fields optional, for PATCH. **Out** = what you return. `hashed_password` is never in an `Out` schema, so it can never leak.
* `ConfigDict(from_attributes=True)` lets Pydantic read SQLAlchemy objects.
* `payload.model_dump(exclude_unset=True)` in `utils.apply_updates` gives correct **PATCH** behaviour: only the fields the client sent are changed.

### 3.5 `security.py`: passwords and JWT
* **bcrypt**: one-way hash with a salt. You can verify a password but never decrypt it.
* **JWT**: `header.payload.signature`. The payload (`sub` = user id, `role`, `exp`) is readable by anyone, but only the server's `JWT_SECRET` can produce a valid signature. Paste a token into jwt.io during practice to see this.

### 3.6 `deps.py`: dependencies and RBAC (a demo talking point)
```
endpoint(admin: AdminUser)
   └─ require_roles(ADMIN).checker(user)          -> 403 if the role is wrong
        └─ get_current_user(token, db)            -> 401 if the token is bad or expired
             ├─ oauth2_scheme                     reads the "Authorization: Bearer ..." header
             └─ get_db                            opens the Session
```
`Annotated[User, Depends(...)]` aliases (`CurrentUser`, `AdminUser`, `AdminOrAuditor`) make each endpoint's permission readable in its signature:
```python
def update_equipment(equipment_id: int, payload: EquipmentUpdate, db: DbSession, admin: AdminUser):
```
**401 vs 403:** 401 means "I don't know who you are". 403 means "I know who you are, and you can't do this".

There is also **row-level** security. `visible_to(user)` in `routers/equipment.py:15` adds a `WHERE` clause so farm hands only get their own rows. `get_job_for_user` returns 404, not 403, for other people's jobs, so a farm hand can't even confirm that a job ID exists.

### 3.7 `routers/`: REST endpoints
Standard REST verbs: `GET` (list or read), `POST` (create → **201**), `PATCH` (partial update), `DELETE` (→ **204**). Business rules return **409 Conflict**:
* You can't delete equipment that has job history, because that would corrupt the reliability metrics. Retire it instead.
* You can't delete a farm that still houses equipment.
* A farm hand can't reopen a finished job.

`sync_equipment_status` (`jobs.py:32`) is domain logic: starting a job puts the machine **In-Use**, and finishing the last running job sets it back to **Idle**.

### 3.8 `routers/analytics.py`: SQL aggregation (a demo talking point)
Each question is **one SQL query**. Postgres does the counting, not a Python loop. Compare each query with its raw SQL in `docs/analytics.sql`:

| Question | SQL technique |
| --- | --- |
| Low fuel | `WHERE status IN (...) AND fuel_level < :threshold ORDER BY` |
| Co-location | Self-join with **aliases** (the farm appears twice in different roles), `IS DISTINCT FROM` (a NULL-safe `!=`) |
| Reliability | `COUNT(*) FILTER (WHERE status='Completed')` and `GROUP BY model` |
| Maintenance flags | `LEFT JOIN` (keeps empty farms), `NULLIF` (no divide-by-zero), **`HAVING`** (filters groups after aggregation) |
| Reporting lines | Two aliases of `users` (supervisor and hand), `COUNT(DISTINCT ...)`, an outer join to active jobs |

Want to see the SQL SQLAlchemy generates? Add `echo=True` to `create_engine` in `database.py` and watch the uvicorn terminal.

### 3.9 `storage.py` and `routers/reports.py`: S3 with boto3 (a demo talking point)
Upload flow:
```
browser FormData(file, notes) ─► POST /api/jobs/{id}/reports (multipart)
   FastAPI: role check → is it your job? → content-type allowlist (415) → size ≤ 10 MB (413)
   boto3.upload_fileobj(...)  → bucket "agricore-service-reports", key service-reports/job-82/<uuid>-name.pdf
   Postgres row: file_url = "s3://agricore-service-reports/service-reports/job-82/..."
```
Download flow: the bucket is **private**. `GET /reports/{id}/download-url` returns a **presigned URL**, a link carrying a signature that S3 honours for 5 minutes. The browser opens it directly.

**Locally**, `S3_ENDPOINT_URL=http://localhost:5001` points boto3 at **moto**, an S3 emulator, so the boto3 calls are the same ones that would run on AWS. Removing that one variable makes the code talk to real S3.

### 3.10 `main.py`: wiring it together
Creates the `FastAPI()` app, adds CORS, mounts every router under `/api`, and defines `handler = Mangum(app)`. That last line is the **AWS Lambda entry point**: Mangum translates Lambda events into ASGI requests.

### 3.11 `seed.py` and `tests/`
* The seed uses `random.Random(17)`, so data is **deterministic**. The dashboard numbers are the same every rehearsal.
* `tests/` run against a separate `agricore_test` database and moto's in-memory S3. `test_analytics.py` asserts the known answers (7, 5, 2 flagged, and so on).

---

## Part 4: Frontend, file by file

### 4.1 `main.jsx`: providers
```jsx
<ThemeProvider> → <BrowserRouter> → <NotifyProvider> → <AuthProvider> → <App/>
```
Each provider makes something available to everything inside it.

### 4.2 `context/AuthContext.jsx`: React Context API (a demo talking point)
* `createContext` + `<AuthContext.Provider value={...}>` + `useAuth()` hook.
* Holds `user` and `token`, plus `login()`, `logout()` and `hasRole(...)`.
* Persists the token in `localStorage` so a page refresh keeps you logged in, and validates it with `/auth/me` on load.
* `setUnauthorizedHandler(logout)` means any 401 anywhere logs you out automatically.
* **Why Context:** without it, you would pass `user` as a prop through Layout → Page → Grid → Dialog ("prop drilling").

### 4.3 `api/client.js`
One place that adds `Authorization: Bearer`, serialises JSON, sends multipart for uploads, and turns Pydantic's 422 error list into a readable sentence. That's how "fuel_level: Input should be less than or equal to 100" appears in the dialog.

### 4.4 `hooks.js`: a custom hook
`useApi('/equipment')` → `{ data, loading, error, reload }`. It uses `useState` for the data and `useEffect` to fetch on mount. Pages call `reload()` after a save.

### 4.5 MUI layout
* `Container` sets a max width with padding. `Box` is a styled div. `Card` is a surface.
* `Grid` (MUI v7) is responsive: `size={{ xs: 6, md: 4, lg: 2 }}` means 2 cards per row on phones, 3 on tablets, and 6 on desktop.
* `sx={{ ... }}` styles any component and uses theme values (`'primary.main'`).

### 4.6 `components/AppDataGrid.jsx`: MUI DataGrid (a demo talking point)
* **Sorting:** click any header. **Pagination:** the footer offers 10, 25, 50 or 100 rows per page.
* **Search:** the search box and the grid share one `filterModel` state. Typing sets `quickFilterValues`, and the grid filters all columns live.
* **Toolbar:** column chooser, column filters, CSV export.
* `renderCell` draws chips and fuel bars inside cells. `valueGetter` computes a cell value.

### 4.7 RBAC in the UI
* `Layout.jsx` filters navigation by role (`NAV` items list their roles).
* Pages render admin buttons only `if (isAdmin)`.
* `RouteGuards.jsx` blocks whole pages.
* **The key point:** these are conveniences. The API enforces the same rules, so a hacked UI still gets 403.

---

## Part 5: Tools you should be comfortable with before demo day

| Tool | Try this |
| --- | --- |
| Swagger UI | http://localhost:8000/docs → **Authorize** (log in as admin) → try `GET /api/analytics/low-fuel` with `threshold=30` |
| psql | `psql postgresql://agricore:agricore@localhost:5432/agricore` then `\dt`, `\d equipment`, `SELECT status, count(*) FROM equipment GROUP BY status;` |
| Raw SQL | `psql postgresql://agricore:agricore@localhost:5432/agricore -f docs/analytics.sql` |
| curl | `curl -s -X POST localhost:8000/api/auth/login -d 'username=admin@prairiecrest.coop&password=AgriCore2026!'` |
| pytest | `cd backend && .venv/bin/pytest -v` |
| Browser DevTools | Network tab → click a grid row action → inspect the request headers (Bearer token) and the JSON response |

---

## Part 6: Exercises (do at least 3, they cement understanding)

1. **Read the SQL.** Set `echo=True` on the engine, reload the dashboard, and match each logged query to a business question.
2. **Break validation on purpose.** In Swagger, POST `/api/equipment` with `"fuel_level": -5`, then `"equipment_type": "Drone"`. Read the 422 responses. Find the `Field(...)` that rejected each one.
3. **Watch RBAC.** In Swagger, log in as the farm hand and call `GET /api/analytics/summary` → 403. Then, as the admin, find a job whose operator isn't Tyler Hansen and call `GET /api/jobs/{that id}` as the farm hand → 404. Explain why one returns 403 and the other 404.
4. **Add a query parameter.** Give `GET /api/jobs` a `search` parameter that filters by title, copying the pattern in `routers/equipment.py`. Add a test.
5. **Change a threshold.** Make the maintenance-flag threshold a dropdown on the dashboard (like the low-fuel 10/20/30 toggle). Hint: `useApi('/analytics/maintenance-flags', { threshold })`.
6. **Decode a JWT.** Log in, copy `agricore_token` from DevTools → Application → Local Storage, and paste it into jwt.io. Find `sub`, `role` and `exp`. Why can't you just edit the role?

---

## Part 7: Glossary

| Term | Meaning |
| --- | --- |
| ASGI | The async server interface FastAPI speaks. Uvicorn is the ASGI server. |
| ORM | Object-Relational Mapper: Python classes ↔ SQL tables (SQLAlchemy) |
| Session | SQLAlchemy's unit of work, which collects changes and commits them in one transaction |
| Dependency injection | FastAPI calls `Depends(...)` functions and passes the results into your endpoint |
| JWT | A signed token that proves identity without a server-side session |
| RBAC | Role-Based Access Control |
| CORS | Browser rule about which origins may call an API |
| Presigned URL | A temporary signed link to a private S3 object |
| Mangum | Adapter that runs an ASGI app (FastAPI) on AWS Lambda |
| moto | A library that emulates AWS services locally and in tests |
| 422 | "Unprocessable Content": Pydantic rejected the request body or query |
