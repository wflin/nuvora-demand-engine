# 02 — System Architecture

## 1. Logical architecture

```text
                    ┌─────────────────────┐
                    │ Research / UI / API │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  Research Service   │
                    └──────────┬──────────┘
                               │
             ┌─────────────────▼─────────────────┐
             │        Source Connector Layer    │
             │ Google / YouTube / GitHub / ...  │
             └─────────────────┬─────────────────┘
                               │
                        DemandSignal[]
                               │
             ┌─────────────────▼─────────────────┐
             │     Normalization / Dedup        │
             └─────────────────┬─────────────────┘
                               │
             ┌─────────────────▼─────────────────┐
             │       Demand Clustering          │
             └─────────────────┬─────────────────┘
                               │
                          Demand[]
                               │
             ┌─────────────────▼─────────────────┐
             │     Opportunity Generator        │
             └─────────────────┬─────────────────┘
                               │
                       Opportunity[]
                               │
             ┌─────────────────▼─────────────────┐
             │      Transparent Scoring          │
             └─────────────────┬─────────────────┘
                               │
             ┌─────────────────▼─────────────────┐
             │ Recommendations / MVP Briefs     │
             └──────────────────────────────────┘
```

## 2. Layer responsibilities

### API layer
Accept requests, validate schemas, return stable API contracts. It must not implement source-specific scraping or scoring logic.

### Research service
Orchestrates a research run and selects connectors according to configuration.

### Connector layer
Owns source-specific collection, rate limits, parsing and mapping into `DemandSignal`. Source-specific response formats never leak into the analysis domain.

### Domain layer
Owns normalization, clustering, opportunity construction and scoring. This layer should be testable without network access.

### Persistence layer
PostgreSQL is the system of record for research runs, signals, demands, opportunities and score evidence.

### AI layer
AI is an interpretation component, not the source of truth. It can summarize, cluster, propose hypotheses and explain evidence. Deterministic source facts must remain separately stored.

## 3. Initial technology direction

- Backend: Python + FastAPI.
- Database: PostgreSQL.
- ORM/data access: SQLAlchemy.
- Migrations: Alembic.
- Frontend: Next.js can be added after the API vertical slice is stable.
- Background execution: start with a simple service/job abstraction; introduce a queue/worker only when collection workloads require it.
- Redis: optional later for rate limiting, caching and dedup acceleration; not a V1 dependency unless required.

## 4. Dependency direction

```text
API → Application Services → Domain
                         ↘ Persistence
                         ↘ Connectors
```

The domain must not import FastAPI, HTTP clients or source-specific modules.

## 5. Reliability requirements

Collection must be idempotent. Temporary provider failures must produce explicit job errors and retryable states. Partial source failure must not erase successful signals from other sources.

## 6. Legacy migration principle

The existing `google-keyword-research` project is a reusable reference and migration source. Its working behavior should be preserved where useful, but the new engine owns the new architecture. The legacy project must not be modified as part of this migration unless explicitly requested.
