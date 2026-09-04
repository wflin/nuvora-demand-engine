# P0-002 Implementation Report

## 1. Summary

P0-002 bootstrapped the runnable backend foundation of the Nuvora Demand
Engine in this repository. It ports the proven Research / Research Job
capability, PostgreSQL schema and Alembic migrations from the legacy
`google-keyword-research` project without modifying that repository, and adds
unified environment-driven settings plus a local Docker PostgreSQL setup.

## 2. Repository State

- Repository: `wflin/nuvora-demand-engine`
- Local root: `D:\source\nuvora\demand-engine`
- Branch: `main`
- Legacy reference: `D:\source\google-keyword-research` (read-only, unchanged)
- Independent repository: yes (no monorepo, no submodule, no mvp-01 content)

## 3. Product Documents Reviewed

- docs/00-PRODUCT-VISION.md: READ
- docs/01-PRD.md: READ
- docs/02-SYSTEM-ARCHITECTURE.md: READ
- docs/03-DATA-MODEL.md: READ
- docs/04-SOURCE-CONNECTORS.md: READ
- docs/05-SCORING-MODEL.md: READ
- docs/06-OPPORTUNITY-MODEL.md: READ
- docs/07-API-SPEC.md: READ
- docs/08-UI-SPEC.md: READ
- docs/09-DEVELOPMENT-PLAN.md: READ
- docs/10-TEST-PLAN.md: READ
- docs/11-ACCEPTANCE.md: READ

No conflicts between the docs and this phase were found. Docs state that
connectors, DemandSignal, clustering and scoring belong to later phases,
which matches the P0-002 scope.

## 4. Architecture Implemented

```text
Browser/Client
   |
   v
FastAPI (apps/api)          API layer: validation + routing only
   |
   v
Services                    Research/Job state machines and job lifecycle
   |
   v
SQLAlchemy + PostgreSQL     research_project / research_job / keyword /
                            research_keyword / keyword_metric_snapshot
```

The application is structured so source connectors, DemandSignal and
versioned `/api/v1` endpoints can be added in later phases without reworking
the foundation.

## 5. Project Structure

```text
demand-engine/
├── README.md
├── pyproject.toml            # root project + pinned dependencies + pytest config
├── docker-compose.yml        # PostgreSQL 16 on host port 5433
├── .env.example
├── .gitignore
├── docs/
│   ├── 00-... / 11-ACCEPTANCE.md   # product docs (from GitHub main)
│   ├── CURRENT-STATUS.md
│   └── P0-002-IMPLEMENTATION-REPORT.md
└── apps/api/
    ├── alembic.ini
    ├── alembic/
    │   ├── env.py
    │   └── versions/0001_initial_empty.py
    │   └── versions/0002_create_research_tables.py
    │   └── versions/0003_create_research_jobs.py
    ├── app/
    │   ├── main.py
    │   ├── core/settings.py          # unified configuration
    │   ├── api/health.py             # /health, /ready
    │   ├── api/research.py           # Research CRUD + run + jobs
    │   ├── api/research_jobs.py      # job detail
    │   ├── db/base.py, session.py, dependencies.py
    │   ├── models/research.py, keywords.py
    │   ├── schemas/research.py, research_job.py
    │   └── services/research.py, research_job.py
    └── tests/                        # ported pytest suite
```

## 6. Database

Database name: `demand_engine` (user `demand_engine`), hosted on host port
`5433` to avoid clashing with other local PostgreSQL instances.

Tables migrated (identical to legacy schema, non-destructive):

- `research_project`
- `research_job`
- `keyword`
- `research_keyword` (legacy compatibility, retained)
- `keyword_metric_snapshot` (legacy compatibility, retained)

## 7. Alembic

- Migrations `0001`, `0002`, `0003` were migrated from the legacy project
  without destructive changes.
- `alembic upgrade head` succeeds from a clean database.
- `alembic current` reports `0003 (head)`.
- `DATABASE_URL` is read from the unified settings module.

## 8. APIs

```text
GET    /health
GET    /ready
POST   /api/researches
GET    /api/researches
GET    /api/researches/{research_id}
PATCH  /api/researches/{research_id}
DELETE /api/researches/{research_id}
POST   /api/researches/{research_id}/run
GET    /api/researches/{research_id}/jobs
GET    /api/research-jobs/{job_id}
```

Versioned `/api/v1` interfaces are deferred per docs/07 (new interfaces use
`/api/v1` starting with later phases).

## 9. Tests

Test command: `python -m pytest -v` (run from the repository root with the
venv active and PostgreSQL running).

Result: `200 passed`.

The suite covers health/readiness, CORS, database connectivity, models
(create/read/unique/FK/cascade), Research CRUD + status state machine,
ResearchJob state machine + API, and the Alembic environment.

## 10. Legacy Migration

### Migrated from google-keyword-research

- SQLAlchemy models: `research_project`, `research_job`, `keyword`,
  `research_keyword`, `keyword_metric_snapshot`, `normalize_keyword`.
- Alembic migrations `0001`-`0003` and `alembic.ini`.
- Research CRUD API, Research Job API, health/readiness endpoints.
- Research/Job state machines and job lifecycle service.
- Pydantic schemas, DB session/dependency layer.
- Test suite (adapted only for import paths and alembic config location).

### Not migrated (deliberately)

- Google Suggest / Google Trends providers and their tests: belong to
  P0-003 (Google connector) per docs/09.
- Provider abstraction/registry and provider tests: same reason.
- Next.js web application: the frontend is out of scope until the API
  vertical slice is stable (docs/02, docs/08).
- Legacy docs folder: the Demand Engine owns its own docs (00-11).

## 11. Known Issues

- `DATABASE_URL` must be present in the environment at import time for the
  API and Alembic; no `.env` auto-loading is implemented (same behavior as
  the legacy project). Documented in `.env.example` and README.
- Docker Compose exposes PostgreSQL on host port `5433`; tools that assume
  `5432` need the matching `DATABASE_URL`.

## 12. Deferred Work

Explicitly deferred to later phases:

- P0-003 Google connector (Suggest/Trends providers, collection)
- P0-004 DemandSignal model, normalization, fingerprinting, idempotent writes
- P0-005 Research integration with `/api/v1` endpoints
- P0-006 Test/quality gate (duplicate collection, partial provider failure)
- P0-007 V1 acceptance with real Google capability
- P1: Demand clustering, cross-source corroboration, opportunity generation,
  scoring v1.0, opportunity API
- P2: YouTube / GitHub / Reddit / HN / Product Hunt connectors
- P3: MVP brief generation for the Codex build loop
- Redis, Celery/workers, frontend, auth, payments, Vercel deployment

## 13. Acceptance Result

Matched against docs/11 scope that is relevant to P0-002:

- Repository contains architecture/plan docs: YES (00-11 + this report)
- Local clone and GitHub repo one-to-one: YES
- Legacy repo not modified: YES
- Backend starts locally: YES
- PostgreSQL starts locally: YES
- Alembic migrations run from a clean DB: YES (verified)
- Health/readiness endpoints work: YES
- Research project create/CRUD: YES
- Research run starts and state persists: YES
- Run state/job observability: YES

Google vertical slice (docs/11 D), evidence quality (E), opportunity layer
(F) and product decision (G) belong to P0-003+ and are intentionally NOT
claimed here.

## 14. Git Commit

Filled in by the agent after commit (see final report).

## 15. Push Result

Filled in by the agent after push (see final report).
