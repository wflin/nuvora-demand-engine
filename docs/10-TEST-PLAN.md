# 10 — Test Plan

## Unit tests

- text normalization;
- keyword normalization;
- fingerprint generation;
- source mapping;
- score calculations;
- score versioning;
- evidence classification.

## Connector tests

Network-independent fixtures should cover:

- normal responses;
- empty responses;
- malformed responses;
- duplicate results;
- pagination;
- transient errors;
- source encoding differences where applicable.

## Integration tests

- database migration from a clean database;
- create research project;
- start research run;
- persist signals;
- repeat the same collection and verify idempotency;
- retrieve signals;
- retrieve demand/opportunity data once those layers exist.

## Failure tests

- provider timeout;
- provider rate limit;
- invalid configuration;
- database unavailable;
- one source failing while another succeeds.

## Quality gates

A phase cannot be accepted if:

- tests fail;
- secrets are committed;
- source-specific data leaks into domain contracts;
- metrics are fabricated;
- duplicate collection creates uncontrolled duplicate signals;
- API behavior differs from the documented contract without approval.
