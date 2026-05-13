# Hospital Appointment System (Project 6)

Backend for managing **doctors**, **patients**, and **appointments** with JWT authentication, role-based access (admin / doctor / patient), Redis cache-aside, structured logging, Prometheus metrics, an admin monitoring dashboard, pytest coverage, a simple web UI (bonus), and Docker Compose (bonus).

## Features (course + project)

- **REST** CRUD for doctors and patients; appointments with book, **paginated list** (`items`, `total`, `page`), status updates, **`PUT` reschedule** (patient/doctor: same doctor; admin may reassign doctor), and admin delete.
- **JWT**: register (patient), login (`/auth/login` JSON and `/auth/token` OAuth2 form), protected routes.
- **Roles**: admin manages doctors/patients; doctor views own schedule and updates appointment status; patient books/cancels own appointments.
- **Business rules**: no double-booking for the same doctor (excluding cancelled slots); status lifecycle validation; **no booking in the past** (with small grace window); **minimum and maximum appointment duration** (configurable via env).
- **Auth hardening**: **per-IP rate limiting** on register, JSON login, and OAuth2 token (in-memory; tune via env).
- **Redis**: cache-aside for `GET /doctors` and `GET /patients` (list + by id) with invalidation on create/update/delete.
- **Logging**: request logging middleware (method, route template, status, duration); auth and CRUD logs.
- **Monitoring**: in-memory summary for dashboard + **Prometheus** `GET /metrics`; HTML dashboard at **`/dashboard`** (admin JWT).
- **Tests**: `pytest` + `TestClient` under `tests/` (auth, RBAC, CRUD, double booking, monitoring).

## Quick start (local)

```powershell
cd hospital_appointment
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# optional: edit .env — set REDIS_ENABLED=false if Redis is not running
uvicorn app.main:app --reload
```

- **Swagger UI**: http://127.0.0.1:8000/docs  
- **Health**: http://127.0.0.1:8000/health  
- **Metrics**: http://127.0.0.1:8000/metrics  
- **Monitoring dashboard**: http://127.0.0.1:8000/dashboard (login with bootstrap admin below)  
- **Bonus UI (Arabic)**: http://127.0.0.1:8000/ui/

### Default bootstrap admin

On first startup an admin user is created if missing (change via `.env`):

- Email: `admin@hospital.example.com`  
- Password: `Admin123!`

Patient self-registration: `POST /api/v1/auth/register` (creates linked patient profile).

## Docker Compose (bonus)

From `hospital_appointment`:

```powershell
docker compose up --build
```

API: http://localhost:8000 — uses PostgreSQL + Redis as in `docker-compose.yml`.

## Git / GitHub (mandatory for grading)

Use **feature branches**, **pull requests**, and **meaningful commits** so each member’s work is visible. This sample repo can be initialized with `git init` and pushed to GitHub; add teammate names and roles in this README under **Team**.

## Team

| Name | Role / contribution |
|------|---------------------|
| _Add members_ | _e.g. API, tests, Docker, UI_ |

## Project layout

```
hospital_appointment/
  app/
    main.py            # FastAPI app, lifespan, /health, /metrics, /dashboard
    config.py
    database.py
    dependencies.py
    models/
    schemas/
    routers/
    services/          # business logic + Redis cache-aside
    middleware/
    utils/
  frontend/            # bonus static UI
  static/              # monitoring dashboard HTML
  tests/
  Dockerfile
  docker-compose.yml
  requirements.txt
```

## Performance note (caching)

With Redis enabled, repeated `GET /doctors` and `GET /patients` should respond faster after the first load; writes invalidate affected keys (`doctors:all`, `doctors:id:{id}`, etc.).
