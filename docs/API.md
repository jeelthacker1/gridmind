# API and operations

Interactive OpenAPI documentation is available at `http://localhost:8000/docs`, with machine-readable schema at `/openapi.json`. Browser requests proxy through Next.js `/api/*`, so authentication cookies remain same-origin.

| Endpoint | Purpose | Role |
|---|---|---|
| GET /api/health | Database readiness | Public |
| POST /api/login, /api/logout | Create/revoke opaque cookie session | Login / signed in |
| GET /api/me | Current role | Viewer+ |
| POST /api/users | Add user with hashed password | Admin |
| GET /api/factories | List configuration snapshots | Viewer+ |
| POST /api/factories | Save configuration as a new scenario | Analyst+ |
| GET /api/datasets | List immutable dataset versions | Viewer+ |
| POST /api/datasets/import | Validated multipart CSV upload | Analyst+ |
| GET /api/datasets/{id}/csv | Download readings | Viewer+ |
| POST /api/runs | Queue forecast, optimization or scenario job | Analyst+ |
| GET /api/runs, /api/runs/{id} | Read stored status/results | Viewer+ |
| POST /api/simulations/{run_id} | Create playback | Analyst+ |
| POST /api/simulations/{id}/control | Start, pause, resume, speed, seek, reset | Analyst+ |
| GET /api/simulations/{id}/events | SSE stream of authoritative playback | Viewer+ |
| GET /api/reports/{id}?format=csv&period=daily | Stored-run report | Viewer+ |
| GET /api/audit | Latest 100 audit records | Admin |

Example run body:

```json
{
  "kind": "scenario",
  "dataset_id": 1,
  "horizon": 24,
  "config": {"profile": "small", "capacity": 200, "power": 80},
  "changes": {"tariff_scale": 1.25}
}
```

`kind` is `forecast`, `optimization` or `scenario`; `horizon` is 24 or 168 hours. Omit `forecast_id` for historical replay, or reference a completed forecast belonging to the same dataset. `changes` is validated against the full asset configuration. `outage_start` is elapsed hours from the selected horizon start, not a timestamp.

For CSV uploads, optional multipart fields are `timezone` (IANA, default UTC), `unit` (W/kW/MW), and `outliers` (reject/clip). Required columns are timestamp, demand_kw, solar_kw, import_price, export_price. Rows must be ascending and unique, with regular 15-minute/hourly spacing, finite nonnegative values and export price ≤ import price. Limits are 5 MB and 35,136 rows. Original upload SHA-256 and handling warnings are stored.

Report formats are CSV/PDF. Periods are daily, weekly, monthly, forecast and scenario. Daily/weekly/monthly group **only intervals in the stored run**, not a full month extrapolation. Forecast reports export held-out predictions and actuals; scenario reports export before/after/difference metrics. Raw per-interval dispatch is available from the run API. Audit records include mutations and report exports.

Sessions are random opaque tokens; only SHA-256 token digests are stored. Passwords use salted scrypt. Cookies are HTTP-only, SameSite Strict and optionally Secure. Non-safe methods enforce configured browser origins and reject cross-site fetch metadata. Login is limited to 20 attempts/minute per immediate peer; Redis provides the shared counter in Compose, with an in-process development fallback. Because Next.js is the proxy, peer-based limits may be shared by users behind it. Configure a trusted reverse-proxy identity policy before public deployment.

## Operations

```sh
docker compose ps
docker compose logs -f api worker
docker compose exec api alembic current
docker compose exec postgres pg_dump -U gridmind gridmind > backup.sql
```

Do not run multiple migrations concurrently. The worker depends on the migrated/seeded healthy API. PostgreSQL and Redis have no host-published ports. Back up PostgreSQL volumes before upgrades. Runtime credentials and meter uploads should not be committed to Git. `docker compose down` preserves data; adding `-v` destroys it.
