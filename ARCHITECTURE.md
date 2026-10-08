# Student Portal — production architecture

TGM Education · 8 October 2026

## Hosting and release process

The deployment uses two Vercel projects: the existing React/Vite frontend at https://tgm-student-portal-frontend.vercel.app/ and a separate Django REST Framework backend named `tgm-student-portal-backend`. The backend repository is `EdetDavid/tgm_education_student_portal` and contains Django directly at its root; the frontend repository is `EdetDavid/tgm_student_portal_frontend`. Do not use the workspace's legacy combined root configuration for either project. Vercel detects the backend's `manage.py`, loads `config.wsgi.application`, installs Python dependencies and collects static files for CDN delivery. A managed Gunicorn container remains a future option for long-running jobs, not the selected deployment. [Vercel Django deployment](https://vercel.com/docs/frameworks/full-stack/django).

The frontend's `vercel.json` points to the deployed backend at https://tgm-student-portal-backend.vercel.app and creates external rewrites for `/api/*` and `/static/rest_framework/*`; `/admin/` resolves to the React entry point. Browsers keep the frontend origin, so Django's Secure, HttpOnly session cookie works without cross-site cookie exceptions. Django trusts the exact frontend HTTPS origin for CSRF and permits only explicitly configured hosts. All API responses carry private/no-store cache headers to keep session tokens and inquiries out of shared CDN caches. A project being created does not prove deployment: the API, migrations, submission and login flows must pass production smoke tests before the backend is considered live. [Vercel rewrites](https://vercel.com/docs/routing/rewrites).

Put Neon PostgreSQL in a region close to the API, use separate production/staging databases and secret stores, and give preview deployments only synthetic data. Build and run API tests, browser tests and migration checks in CI before release. Run `scripts/release.py` once as a release job, not whenever a request starts; it rejects local database URLs, checks production settings, migrates and optionally seeds synthetic records. Deploy backward-compatible schema changes before their consumers, retain the previous Vercel deployment for rollback, and test the complete login/submission flow before directing event traffic to a release. Run Django's deployment checks against the actual production environment. [Django deployment checklist](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/).

## Verified deployment status

The production API is https://tgm-student-portal-backend.vercel.app/api/; the frontend proxies it successfully. Neon has 20 sample courses, 3 events and 240 synthetic inquiries. Production smoke checks passed for catalog access, submission, duplicate references, CSRF-protected staff login, session persistence across requests and dashboard access. The check removed only its temporary account, session and inquiry. A permanent production admin still needs creating (or explicit approval to copy the existing local staff login); local credentials were not transferred. Local PostgreSQL data was not changed by this cloud release.

## Database design

This workspace uses local PostgreSQL (`tgm_studentportal`); SQLite remains available for isolated browser tests and as a migration backup. Production uses hosted PostgreSQL through `POSTGRES_URL`, with `DATABASE_URL` accepted for Marketplace integrations. Production settings refuse to start without a secret and a PostgreSQL connection string. Vercel cannot use `localhost:5433` on the developer's laptop. Use Neon's pooled TLS connection for runtime traffic; server-side cursors are disabled and persistent Django connections are disabled on Vercel. Production database provisioning requires an authorized Neon account or Vercel Marketplace installation; no cloud database is implied by the local PostgreSQL migration.

| Entity     | Responsibility and relationships                                                                                                                                                            |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Student    | Canonical identity with case-insensitively unique email and latest name, phone and location; one student has many inquiries.                                                                |
| Inquiry    | Exactly one protected student, course and event relationship; reference, intake, destination, status, notes and submission timestamp. Contact details are retained as submission snapshots. |
| Course     | Name, level, current tuition in NGN, intakes, study location and active flag. Deactivation preserves history.                                                                               |
| Event      | Name, city, venue, date, time and capacity. Events with linked inquiries cannot be deleted.                                                                                                 |
| Admin user | Django's auth user, with hashed passwords and session authentication; never a plaintext-password table.                                                                                     |

Snapshot contact details explain what the student submitted at that time; later contact changes do not silently rewrite old inquiries. Course names and prices are deliberately read from the related course, so staff edits propagate everywhere. Potential revenue is current tuition multiplied by matching inquiries, not money received. Course analytics group by course ID so two courses with the same name are not merged.

Duplicate handling normalizes email and reuses the reference for the same student/course/event within a rolling 24-hour window. PostgreSQL locks the student row inside the create transaction before checking for a duplicate, serializing concurrent submissions for that student. Different courses/events remain separate inquiries; a submission after the window is new. SQLite does not provide equivalent row locking and is not the production concurrency target.

## Search and indexing

Both student course search and staff inquiry search run against the database. Staff searches use case-insensitive substring matches on name, email, phone and reference. Filters, dashboard aggregates and CSV export share one validated query builder. Pagination is deterministic, with an ID tie-breaker.

The schema has a unique reference index, a case-insensitive email uniqueness constraint, a student/course/event/date index for duplicate checks, and indexes for recent records, status/date, course/date, event/date, intake and destination. Foreign keys also receive indexes. Ordinary B-tree indexes do not solve arbitrary substring searches: PostgreSQL migrations add `pg_trgm` GIN indexes on the `UPPER(...)` expressions used by Django's `icontains` queries, including student location and course fields. SQLite uses database scans for this small demo. Inspect production query plans before adding more indexes, since indexes consume storage and slow writes. [PostgreSQL trigram index support](https://www.postgresql.org/docs/17/pgtrgm.html#PGTRGM-INDEX).

Use Neon's pooled endpoint for application traffic and its direct endpoint for administrative/migration jobs when appropriate. Configure a restore window that meets the agreed recovery objective, keep separate encrypted exports, and perform a restore drill before the exhibition. Do not assume a provider plan's default retention is sufficient. [Neon pooling](https://neon.com/blog/pgbouncer-the-one-with-prepared-statements), [Neon branch restore](https://neon.com/blog/announcing-point-in-time-restore).

## Security and role-based access

The implemented build requires staff authentication for every admin endpoint, not just the frontend route. Session-authenticated writes require CSRF, passwords use Django hashing, production cookies are Secure/HttpOnly where applicable, hosts/origins are explicit, and ORM queries avoid interpolating user-supplied SQL. React escapes ordinary text; CSV export escapes formula-like values. Student-facing endpoints cannot list private inquiries. Validate inputs on both sides, but always treat server validation as authoritative.

Before going live I would add provider/WAF login and submission rate limits, staff MFA/SSO, an append-only audit trail for sensitive actions, and centralized error/latency monitoring without student details in logs. Restrict database credentials to the application's database, rotate secrets, use TLS on both network legs, and never put secrets in `VITE_*` variables. Agree retention/deletion rules for contact information and expired sessions, restrict CSV access, and review permissions regularly.

The build currently has one staff role; multiple roles are an optional extension. I would use Django Groups/Permissions enforced by DRF for this separation:

| Role              | Allowed access                                                                               |
| ----------------- | -------------------------------------------------------------------------------------------- |
| Public student    | Read active courses/upcoming events; submit interest; no access to existing student records. |
| Support staff     | Read assigned inquiries and update status/notes; no catalogue changes or bulk exports.       |
| Catalogue manager | Manage courses/events and review demand; no user administration.                             |
| Analyst           | Aggregated analytics, without unnecessary contact details.                                   |
| Administrator     | Assign roles, approve exports and administer the platform.                                   |

Hide unavailable controls for usability, but enforce these permissions at every API endpoint and queryset. Deny access by default. Add role-specific tests before enabling the proposed roles.
