# Current Status

> Single source of truth for Demand Engine development status. Updated at the
> end of every phase.

## Phase status

- P0-001 Legacy audit = DONE
- P0-002 Bootstrap engine = DONE

## P0-002 notes

- Repository: https://github.com/wflin/nuvora-demand-engine
- Backend foundation implemented under `apps/api`:
  - Python project configuration (`pyproject.toml`, pinned dependencies)
  - FastAPI application with unified settings
  - PostgreSQL + SQLAlchemy + Docker Compose (host port 5433)
  - Alembic migrations `0001`-`0003` migrated from the legacy project
  - Research CRUD API + Research Job API (legacy-compatible `/api` paths)
  - Research/Job state machines
  - Health/readiness endpoints
  - Ported tests: 200 tests, all passing
- Out of scope for P0-002 (next phases):
  - Google connector, DemandSignal, clustering, opportunity, scoring, AI
  - Worker/Redis/Celery, frontend, auth, payments, Vercel
- Legacy reference repository `google-keyword-research` was NOT modified.

## Repository layout

```text
apps/api/
    alembic/            # Alembic migrations 0001-0003
    app/
        api/            # HTTP routers (health, research, research jobs)
        core/           # Unified settings
        db/             # SQLAlchemy engine/session/dependencies
        models/         # ResearchProject, ResearchJob, Keyword, ...
        schemas/        # Pydantic request/response schemas
        services/       # Research/Job state machines + job service
        main.py
    tests/              # pytest suite
docs/                   # Product/architecture docs and implementation reports
```
