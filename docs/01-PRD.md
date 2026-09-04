# 01 — Product Requirements

## 1. Users

Primary user: Nuvora founder/operator.

The user needs to:

- search a topic, market or seed keyword;
- inspect evidence from multiple sources;
- discover related needs they did not explicitly search for;
- compare opportunities;
- understand why an opportunity ranks highly;
- decide whether to build an MVP.

## 2. Functional requirements

### FR-01 Research creation
Create a research project with:

- seed query/topic;
- country/market;
- language;
- source selection;
- optional date window;
- optional collection limits.

### FR-02 Source collection
A research run can invoke one or more source connectors. Each connector returns normalized `DemandSignal` records and retains source-specific raw evidence.

### FR-03 Signal normalization
Normalize text, language, country, timestamps and source metadata. Generate a stable fingerprint for deduplication.

### FR-04 Evidence preservation
Store enough original information to reproduce or audit the interpretation. Raw source data must remain separate from normalized fields.

### FR-05 Demand clustering
Group semantically related signals into candidate user needs. Clustering must retain the member signals so the evidence chain remains inspectable.

### FR-06 Opportunity generation
For a demand cluster, generate an opportunity candidate containing:

- problem statement;
- target user;
- proposed product form;
- evidence summary;
- competition summary;
- buildability hypothesis;
- monetization hypothesis;
- open validation questions.

### FR-07 Opportunity scoring
Calculate a transparent score from defined components. Every component must expose its evidence or explain that it is a hypothesis.

### FR-08 Opportunity comparison
Allow sorting/filtering by score, demand strength, growth, competition, build difficulty, monetization and freshness.

### FR-09 Recommendation
For a selected opportunity, generate a concise recommendation:

- why now;
- who has the problem;
- evidence;
- what to build first;
- what not to build;
- fastest validation method;
- key risks.

### FR-10 Research history
Persist research runs and their status so results can be revisited and compared.

## 3. Non-functional requirements

- Python backend with PostgreSQL.
- API versioning under `/api/v1` for new interfaces.
- Deterministic normalization and scoring where possible.
- Idempotent collection writes.
- Structured logs and explicit error states.
- Unit/integration tests for each production connector and core service.
- No fabricated third-party metrics.
- Secrets only through environment/configuration; never committed.

## 4. Explicit non-goals for V1

- Full autonomous product development.
- Automatic paid advertising.
- Guaranteed prediction of product success.
- Purchasing proprietary search-volume datasets.
- Building every source connector at once.
- A complex multi-tenant SaaS permission system.

## 5. Success criteria

V1 is successful when a user can enter a seed topic and obtain a persisted, inspectable opportunity candidate whose score can be traced to collected evidence, with no manual database intervention.
