# Validation record

Initial local verification (16 November 2026):

- Python 3.13.3: **22 pytest tests passed** (24.74 seconds), including real API/import/forecast/dispatch/report integration.
- Next.js 15.5.29 production build: compiled, type-checked and generated successfully.
- Playwright Chromium operator journey: **passed** (4.5 seconds total), including forecast, dispatch, simulation playback, tariff/outage comparison and CSV download.
- Playwright desktop/mobile presentation check: **passed** (2.2 seconds total); screenshots inspected, mobile horizontal page overflow assertion passed.
- Frontend dependency audit after PostCSS override: **0 vulnerabilities**.
- Alembic migration and seeded SQLite development database: executed successfully.
- Measured case studies: executed for all three profiles; see CASE_STUDIES.md.

Final checks and GitHub Actions results will be recorded after publication.

## Environment limitation

Docker CLI is available locally, but Docker Desktop's Linux engine was stopped and `docker desktop start` terminated unexpectedly. Full Compose startup therefore requires verification on GitHub Actions or another working Docker host; a local successful Docker launch is not claimed.

## Scope and known limitations

- Educational planning/digital-twin application; not an approved real-time electrical controller.
- Shared local workspace, not multi-tenant isolation; no MFA, password-reset email or account self-service.
- Day/week optimization horizon; monthly exports aggregate the available run coverage rather than create a full monthly simulation.
- No production-job load shifting, AC power-flow solution, calibrated forecast uncertainty, real weather API or battery degradation physics.
- Historical replay assumes perfect knowledge; forecast-based dispatch is not a realized closed-loop forecast-error backtest.
- Solar-retained and carbon figures follow the documented simplified accounting assumptions.
- Meter data uses JSON snapshots for simplicity, not a scalable time-series schema.
- Starting configurations and datasets are saved as new snapshots; the UI does not overwrite past results.
- RQ infrastructure is the production local stack; direct local tests use inline jobs and SQLite. CI's Compose check covers PostgreSQL/Redis startup.
- The current UI provides role-based controls, while user provisioning and audit review are available through the admin API.
