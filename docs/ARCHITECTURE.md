# Architecture

```mermaid
flowchart LR
    Browser[Next.js dashboard] -->|HTTP-only cookie / REST| API[FastAPI]
    API -->|SSE playback| Browser
    API --> PG[(PostgreSQL)]
    API --> Redis[(Redis queue)]
    Redis --> Worker[RQ worker]
    Worker --> Data[Validated dataset]
    Data --> Forecast[Recursive demand forecasting]
    Data --> Dispatch[HiGHS constrained dispatch]
    Forecast --> Dispatch
    Dispatch --> PG
    Forecast --> PG
    PG --> Reports[Stored-result CSV / PDF]
    Reports --> Browser
```

The API is authoritative for simulation playback. The browser never advances SOC or computes savings. A playback record stores its run, cursor, speed, playing flag and wall-clock update time. Server requests materialize elapsed time into the cursor; reopening a stream resumes the persisted state. Reset and seek affect playback, not the immutable dispatch result.

RQ workers read the persisted request and dataset, perform calculations, and write status/results. The development-only `JOB_MODE=inline` executes the same function without Redis. Failures are persisted and surfaced to the UI. Jobs have a 600-second timeout; each HiGHS solve has a 60-second limit and rejects unsuccessful solves.

## Physical schema

```mermaid
erDiagram
    users ||--o{ login_sessions : authenticates
    users ||--o{ runs : creates
    users ||--o{ audit_logs : acts
    factories ||--o{ energy_assets : owns
    datasets ||--o{ runs : supplies
    runs ||--o{ simulation_runs : plays
    runs ||--o{ scenario_events : changes
    users { int id PK string email UK string password string role }
    factories { int id PK string name json config }
    energy_assets { int id PK int factory_id FK string kind json configuration }
    datasets { int id PK string source json metadata_json json rows datetime created }
    runs { int id PK string kind string status int dataset_id FK int user_id FK json request json result }
    simulation_runs { int id PK int run_id FK int cursor int speed bool playing float updated }
    scenario_events { int id PK int run_id FK json changes }
    audit_logs { int id PK int user_id FK string action datetime created }
```

Consumption readings, solar readings and tariff plans are stored together as immutable, aligned dataset JSON rows. Asset configurations are factory snapshots. Forecast runs, optimization runs and scenario comparisons share the indexed `runs` table, discriminated by `kind`. This compact schema deliberately uses fewer physical tables than the conceptual brief while preserving those data types. It is suited to local scenarios, not high-volume meter telemetry; time-series normalization/partitioning is a future scale-out migration.

Indexes cover run kind, creation time and scenario-run linkage. User email is unique; roles have a database check constraint. Foreign keys link runs, datasets, users and playback. Alembic revision `001` creates the schema; application startup does not silently create tables.

All signed-in users share a single local workspace. Viewers can inspect and export all runs; analysts can import, configure and calculate; only admins can create users or read audit logs. This is intentional shared-workspace authorization, not tenant isolation.
