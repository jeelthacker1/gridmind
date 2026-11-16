# Validation record

Initial local verification (16 November 2026):

- Python 3.13.3: **22 pytest tests passed**, including real API/import/forecast/dispatch/report integration. Final run after security updates: 6.68 seconds (two upstream test-client deprecation warnings).
- Next.js 15.5.29 production build: compiled, type-checked and generated successfully.
- Playwright Chromium final run: **2 tests passed in 8.1 seconds**, including forecast, dispatch, simulation playback, tariff/outage comparison, CSV download and desktop/mobile presentation. Screenshots inspected; mobile horizontal page overflow assertion passed.
- Frontend dependency audit after PostCSS override: **0 vulnerabilities**.
- Python dependency audit after FastAPI/Starlette/multipart/pytest updates: **no known vulnerabilities found**.
- An actual daily PDF export was rendered with Poppler and visually inspected; table text, units and coverage disclosure were legible without clipping.
- Alembic migration and seeded SQLite development database: executed successfully.
- Measured case studies: executed for all three profiles; see CASE_STUDIES.md.

GitHub Actions [run 43869215998](https://github.com/jeelthacker1/gridmind/actions/runs/43869215998) completed successfully on the implementation commit `c2e112e`:

- **test**: Linux dependency installation, all Python tests, Alembic migration/seed, Next.js production build and both Playwright tests passed.
- **compose**: `docker compose up --build --wait` started all five healthy services, the proxied API health check passed, and `scripts/smoke.py` authenticated, loaded PostgreSQL-backed data and completed a Redis/RQ optimization with persisted results.

## Environment limitation

Docker CLI is available locally, but Docker Desktop's Linux engine was stopped and `docker desktop start` terminated unexpectedly. Full Compose startup was verified on GitHub Actions instead; a successful launch on this Windows machine is not claimed.

## Scope and known limitations

- Educational planning/digital-twin application; not an approved real-time electrical controller.
- Shared local workspace, not multi-tenant isolation; no MFA, password-reset email or account self-service.
- Day/week optimization horizon; monthly exports aggregate the available run coverage rather than create a full monthly simulation.
- No production-job load shifting, AC power-flow solution, calibrated forecast uncertainty, real weather API or battery degradation physics.
- Historical replay assumes perfect knowledge; forecast-based dispatch is not a realized closed-loop forecast-error backtest.
- Solar-retained and carbon figures follow the documented simplified accounting assumptions.
- Meter data uses JSON snapshots for simplicity, not a scalable time-series schema.
- Starting configurations and datasets are saved as new snapshots; the UI does not overwrite past results.
- RQ infrastructure is the production local stack; direct local tests use inline jobs and SQLite. CI's Compose check covers PostgreSQL/Redis startup and a real queued dispatch.
- The current UI provides role-based controls, while user provisioning and audit review are available through the admin API.
