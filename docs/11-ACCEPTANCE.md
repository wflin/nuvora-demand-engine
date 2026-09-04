# 11 — V1 Acceptance Criteria

## A. Repository

- [ ] Repository contains documented architecture and implementation plan.
- [ ] Local clone and GitHub repository remain one-to-one.
- [ ] No legacy repository is modified as part of engine bootstrap.

## B. Runtime

- [ ] Backend starts locally.
- [ ] PostgreSQL starts locally.
- [ ] Alembic migrations run successfully from a clean database.
- [ ] Health and readiness endpoints work.

## C. Research

- [ ] User can create a research project.
- [ ] User can start a research run.
- [ ] Run state is persisted.
- [ ] Collection statistics and errors are observable.

## D. Google vertical slice

- [ ] Google provider returns usable test data without requiring the domain layer to know Google response formats.
- [ ] Connector maps source results into `DemandSignal`.
- [ ] Signals are normalized and fingerprinted.
- [ ] Re-running the same collection is idempotent.
- [ ] Raw/source evidence is retained according to source/data policy.

## E. Evidence quality

- [ ] No search volume, CPC, competition or other metric is fabricated.
- [ ] Source facts and AI hypotheses are distinguishable.
- [ ] Important recommendations can be traced to signals.

## F. Opportunity layer

For the full V1 intelligence milestone:

- [ ] Related signals form a demand cluster.
- [ ] A cluster can produce an opportunity candidate.
- [ ] Opportunity score uses model `v1.0`.
- [ ] Every score dimension exposes evidence or missing-data status.
- [ ] Opportunity detail explains why it is recommended.

## G. Product decision

A research run is not considered successful merely because data was collected. The final milestone requires at least one actionable opportunity with a clear target user, problem, evidence chain, MVP hypothesis and validation experiment.
