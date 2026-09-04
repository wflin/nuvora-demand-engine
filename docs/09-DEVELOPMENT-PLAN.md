# 09 — Development Plan

## Delivery strategy

Build one complete vertical slice first. Do not build ten connectors and an empty platform.

## P0 — Foundation

### P0-001 Legacy audit — DONE
Audit `google-keyword-research`, identify reusable code, tests, migrations and limitations.

### P0-002 Bootstrap engine

Goal: create the runnable backend foundation in this repository.

Scope:

- Python project configuration.
- FastAPI application.
- PostgreSQL + SQLAlchemy.
- Alembic migrations 0001–0003 migrated/adapted without destructive changes.
- settings/configuration.
- health/readiness endpoints.
- research CRUD compatibility.
- research job model/state handling.
- tests and local Docker setup.

Explicitly out of scope:

- DemandSignal implementation.
- Google connector integration.
- AI clustering.
- Reddit/YouTube/GitHub connectors.
- Redis.
- frontend.

Acceptance: application starts, database migrates to the expected head, existing core behavior is covered by tests.

### P0-003 Google Connector

Implement:

`ResearchRun → GoogleConnector → Google providers → DemandSignal[] → persistence`

Reuse tested Google Suggest/Trends provider behavior from the legacy project without changing the legacy repository.

### P0-004 DemandSignal

Implement the canonical signal model, normalization, fingerprinting, idempotent persistence and source metadata.

### P0-005 Research integration

Connect the Google collector to the research run orchestration and `/api/v1` endpoints.

### P0-006 Test/quality gate

Add unit, integration and failure-path tests. Verify duplicate collection, partial provider failure and malformed source data.

### P0-007 V1 acceptance

Run a real end-to-end research against an allowed public Google capability and verify an inspectable persisted result.

## P1 — Demand intelligence

- Demand clustering.
- Cross-source corroboration.
- Opportunity generation.
- Evidence graph.
- Scoring v1.0.
- Opportunity API.

## P2 — More sources

Add one connector at a time, prioritizing YouTube, GitHub and Reddit according to evidence quality and technical feasibility.

## P3 — Product factory integration

Generate an MVP brief that can be handed to Codex, including:

- target user;
- problem;
- value proposition;
- MVP scope;
- acceptance criteria;
- suggested stack;
- launch/monetization hypothesis.

## Working method

For each phase:

1. ChatGPT updates requirements/architecture.
2. User confirms direction when the change is product-level.
3. Codex implements the scoped task.
4. Codex runs tests and commits/pushes.
5. ChatGPT reviews the implementation against this repository's docs.
6. Only then move to the next phase.
