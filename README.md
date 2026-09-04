# Nuvora Demand Engine

Nuvora Demand Engine is the internal global demand discovery system for the Nuvora product factory.

## Mission

Continuously discover real user needs from global public signals, validate them across sources, rank product opportunities, and feed the best opportunities into an MVP build-and-learn loop.

> Explore. Build. Learn.

## Core loop

`Global sources → Demand Signals → Demand Clusters → Opportunities → Scoring → MVP Recommendation → Build → Launch → Feedback → Rediscovery`

## What this system is

- A multi-source demand intelligence engine.
- A transparent evidence system: every important conclusion should be traceable to source evidence.
- A product opportunity ranking system that considers demand, growth, competition, buildability and monetization.
- An internal decision-support system for deciding **what to build next**.

## What this system is not

- Not only a Google keyword research tool.
- Not an opaque AI idea generator.
- Not a generic analytics dashboard.
- Not the product itself; it is the discovery engine behind the Nuvora product factory.

## Source strategy

Google is the first connector because the existing Google Keyword Research project provides reusable provider implementations and tests. Future connectors are designed behind the same normalized boundary:

- Google
- YouTube
- GitHub
- Reddit
- Hacker News
- Product Hunt
- App Store / Google Play where feasible
- Other public sources as validated

## Architecture boundary

`Source Connector → DemandSignal → Analysis/Clustering → Opportunity → Scoring → Recommendation`

Connectors collect and normalize evidence. They must not contain the final opportunity judgment logic.

## Documentation

- [Product Vision](docs/00-PRODUCT-VISION.md)
- [PRD](docs/01-PRD.md)
- [System Architecture](docs/02-SYSTEM-ARCHITECTURE.md)
- [Data Model](docs/03-DATA-MODEL.md)
- [Source Connectors](docs/04-SOURCE-CONNECTORS.md)
- [Scoring Model](docs/05-SCORING-MODEL.md)
- [Opportunity Model](docs/06-OPPORTUNITY-MODEL.md)
- [API Specification](docs/07-API-SPEC.md)
- [UI Specification](docs/08-UI-SPEC.md)
- [Development Plan](docs/09-DEVELOPMENT-PLAN.md)
- [Test Plan](docs/10-TEST-PLAN.md)
- [Acceptance](docs/11-ACCEPTANCE.md)

## Delivery rules

1. Product direction is decided by the user.
2. Product requirements and architecture are maintained in this repository.
3. Codex implements the approved tasks and reports test/deployment results.
4. No connector may invent metrics that the source does not provide.
5. AI-generated conclusions must retain an evidence chain.
6. MVP first: implement one complete vertical slice before adding many sources.
7. Legacy repositories are read-only references unless explicitly approved otherwise.

---

## Current phase

- P0-001 Legacy audit: DONE
- P0-002 Backend foundation: DONE
- P0-003+ (Google connector, DemandSignal, clustering, opportunities, AI):
  NOT started. See [docs/09-DEVELOPMENT-PLAN.md](docs/09-DEVELOPMENT-PLAN.md).

## Getting started (P0-002 backend foundation)

### Tech stack

- Python 3.12+ / FastAPI / SQLAlchemy 2.x / Alembic
- PostgreSQL 16 (local development via Docker Compose)
- Pytest for tests

### Local environment requirements

- Python 3.12 or newer
- Docker with Docker Compose
- Git

### Start PostgreSQL

```bash
docker compose up -d postgres
```

PostgreSQL is exposed on host port `5433` (database `demand_engine`, user
`demand_engine`) to avoid clashing with another local PostgreSQL on `5432`.

### Install Python dependencies

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -e ".[dev]"
```

### Configure environment

Copy `.env.example` to `.env` (or export the variables) and make sure
`DATABASE_URL` matches the local PostgreSQL:

```bash
copy .env.example .env          # Windows
# cp .env.example .env          # macOS / Linux
```

### Run migrations

```bash
cd apps/api
..\..\.venv\Scripts\python -m alembic upgrade head    # Windows
# ../../.venv/bin/python -m alembic upgrade head      # macOS / Linux
cd ../..
```

Verify with `python -m alembic current` (expect `0003 (head)`).

### Start the API

```bash
cd apps/api
..\..\.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

API base address: `http://localhost:8000`

- Health: `GET /health`
- Readiness: `GET /ready`
- Interactive docs: `http://localhost:8000/docs`

### Run tests

```bash
python -m pytest -v
```

Database-backed tests require the PostgreSQL container to be running and
`DATABASE_URL` to be set.

### API endpoints implemented in P0-002

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

These endpoints are legacy-compatible. Versioned `/api/v1` interfaces are
introduced in later phases per [docs/07-API-SPEC.md](docs/07-API-SPEC.md).

### Not implemented yet (P0-002)

- Google / YouTube / GitHub / Reddit / Hacker News / Product Hunt connectors
- DemandSignal model and persistence
- Demand clustering, Opportunity, Opportunity Score, AI/LLM analysis
- Background workers, Redis, Celery
- Frontend, user authentication, payments, Vercel deployment

See [docs/P0-002-IMPLEMENTATION-REPORT.md](docs/P0-002-IMPLEMENTATION-REPORT.md)
for the full phase report.
