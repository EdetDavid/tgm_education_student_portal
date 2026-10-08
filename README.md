# Student Portal API

Django REST Framework backend for TGM Education's Student Portal. Frontend: https://tgm-student-portal-frontend.vercel.app/.
Production API: https://tgm-student-portal-backend.vercel.app/api/.

## Local setup (PowerShell)

Requires Python 3.12+ and PostgreSQL. From this repository's root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Create the local PostgreSQL database `tgm_studentportal` and set PGHOST, PGPORT, PGUSER and PGPASSWORD in `.env`; defaults are localhost:5433 and postgres. Never commit passwords. To use SQLite for an isolated demo, clear PGDATABASE and leave POSTGRES_URL empty.

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_demo --inquiries 240
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py runserver
```

API root: http://127.0.0.1:8000/api/. The React frontend is maintained separately in https://github.com/EdetDavid/tgm_student_portal_frontend; Vite proxies /api to port 8000 locally. All tuition/revenue is NGN.

## API and data

- Public: GET /api/courses/ (q, level, location), GET /api/events/, POST /api/inquiries/.
- Staff: /api/admin/csrf/, /api/admin/login/, /api/admin/logout/, /api/admin/me/.
- Staff management: /api/admin/inquiries/, /api/admin/inquiries/{id}/, /api/admin/courses/, /api/admin/events/, /api/admin/dashboard/, /api/admin/filters/.
- DRF browsable API login: /api/auth/login/. Staff access is checked on the server; session writes require CSRF.
- Inquiry search supports partial name, email, phone and reference; shared filters drive pagination, charts and CSV export. The admin reports include course/revenue bars and status/intake/destination/location pie charts.

Student has a case-insensitive unique email. Each Inquiry references exactly one Student, Course and Event; contact fields retain submission snapshots. Course edits propagate through related records; deactivation preserves history. Equivalent student/course/event submissions within 24 hours reuse the reference; PostgreSQL student-row locking serializes the duplicate check.

Seed creates 20 courses, 3 events and 240 synthetic inquiries. Ordinary filter/sort indexes support deterministic pagination; PostgreSQL pg_trgm GIN indexes on UPPER(search fields) support the case-insensitive substring queries used by Django. Migration 0004 enables pg_trgm; the migration role needs that permission. See [ARCHITECTURE.md](ARCHITECTURE.md) for schema, indexing, hosting, security and proposed granular roles. The running build has one staff role.

## Vercel production

Project: **tgm-student-portal-backend**. Import https://github.com/EdetDavid/tgm_education_student_portal with **Root Directory empty**, Framework **Django**, and no custom build/install/output override. Vercel detects manage.py/config.wsgi.application and collects static files automatically. Python runtime is pinned to 3.12.

Use the **tgm-studentportal** Neon Free-plan database linked to this project's Production environment. Runtime uses the pooled TLS URL supplied as POSTGRES_URL or DATABASE_URL; never use localhost or SQLite on Vercel.

Set Production environment variables:

| Variable | Value |
| --- | --- |
| DJANGO_DEBUG | false (Config) |
| DJANGO_SECRET_KEY | Random unique key (Secret) |
| POSTGRES_URL or DATABASE_URL | Hosted pooled PostgreSQL TLS URL (integration-managed) |
| DJANGO_ALLOWED_HOSTS | tgm-student-portal-backend.vercel.app,tgm-student-portal-frontend.vercel.app |
| DJANGO_CSRF_TRUSTED_ORIGINS | https://tgm-student-portal-frontend.vercel.app,https://tgm-student-portal-backend.vercel.app |

Replace backend hostname if Vercel assigns a different one. Keep Preview databases separate and synthetic. Empty CORS configuration is intentional: use frontend same-origin routing, not cross-site cookies.

```powershell
$env:NODE_USE_SYSTEM_CA = '1' # If Node needs Windows' certificate trust store
vercel link --yes --project tgm-student-portal-backend
vercel env pull .env.vercel --environment production
.\.venv\Scripts\python.exe scripts/release.py --env-file .env.vercel --seed-demo --create-admin
vercel git connect https://github.com/EdetDavid/tgm_education_student_portal.git
vercel --prod
```

Release refuses local URLs, runs deployment checks/migrations, optionally seeds synthetic data and prompts for admin credentials. Omit optional flags on subsequent releases. Review security warnings before real event traffic. Vercel redacts Secret values on env pull: release.py replaces a redacted signing key with a temporary management-only key; it does not change the deployed secret. This is safe for migrations, seeding and password creation, which do not issue signed sessions/tokens.

Deploy frontend/vercel.json from the frontend repository; it proxies /api/* and /static/rest_framework/* to https://tgm-student-portal-backend.vercel.app and supports /admin/ refreshes. No frontend API environment variable is required. If changing API hosts, update both external rewrite destinations and redeploy. No secrets belong in VITE_* variables. API responses carry private/no-store cache headers.

Verify backend /api/, /api/courses/, /api/events/ and /static/rest_framework/css/bootstrap.min.css; then verify frontend search, submission/duplicate reference, staff login, reports and CSV. Anonymous admin requests must be denied. Project creation alone is not deployment; confirm the assigned URL and persistence after redeployment.

## Tests

```powershell
.\.venv\Scripts\python.exe manage.py test portal.tests
```

Django uses a separate test database and removes it afterward. PostgreSQL test users need permission to create a test database. Do not point tests at production. Frontend unit and browser tests live in the frontend repository.

Optional production smoke check: `.\.venv\Scripts\python.exe scripts/smoke_production.py`. It uses the ignored cloud profile, creates a temporary staff account and synthetic submission, verifies duplicate handling and authenticated frontend proxy access, then deletes only its own account, session and inquiry. This is a mutating check; run intentionally, not as a passive monitoring job.
