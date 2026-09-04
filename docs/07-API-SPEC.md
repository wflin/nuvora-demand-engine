# 07 — API Specification

New APIs use `/api/v1`.

## Research

### POST `/api/v1/researches`
Create a research project.

Request fields:

- `name`
- `seed_query`
- `country`
- `language`
- `sources[]`
- `date_from` / `date_to` optional
- `limits` optional

### GET `/api/v1/researches`
List research projects.

### GET `/api/v1/researches/{research_id}`
Get project details.

### POST `/api/v1/researches/{research_id}/runs`
Start a research run.

### GET `/api/v1/research-runs/{run_id}`
Get run status and collection statistics.

## Signals

### GET `/api/v1/research-runs/{run_id}/signals`
List normalized signals with source filters and pagination.

### GET `/api/v1/signals/{signal_id}`
Get one signal including raw/source metadata where permitted.

## Demands

### GET `/api/v1/research-runs/{run_id}/demands`
List demand clusters produced from a run.

### GET `/api/v1/demands/{demand_id}`
Get a demand cluster and supporting signals.

## Opportunities

### GET `/api/v1/opportunities`
List/filter opportunities.

Supported filters should include score range, country, source, status and confidence.

### GET `/api/v1/opportunities/{opportunity_id}`
Get full opportunity detail, score breakdown and evidence chain.

### POST `/api/v1/opportunities/{opportunity_id}/rescore`
Create a new score snapshot using the current scoring model.

## Compatibility

Existing legacy research APIs may remain available during migration. They should not block introduction of the versioned API and should be retired only after acceptance confirms no remaining dependency.

## API rules

- Use explicit request/response schemas.
- Return stable error codes.
- Never expose secrets or unnecessary raw credentials.
- Paginate signal-heavy endpoints.
- Include timestamps and model versions where relevant.
