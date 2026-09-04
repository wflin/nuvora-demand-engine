# 04 — Source Connector Specification

## 1. Connector contract

Every source connector implements the same conceptual contract:

```text
collect(request) -> CollectionResult
```

Where `CollectionResult` contains normalized `DemandSignal` candidates, collection statistics, warnings and source-specific diagnostics.

## 2. Connector responsibilities

A connector owns:

- source authentication/configuration where applicable;
- HTTP/client interaction;
- source-specific rate limits;
- pagination;
- source response parsing;
- source-specific retries;
- mapping into `DemandSignal`;
- raw payload preservation.

A connector does not own:

- final opportunity scoring;
- cross-source clustering;
- product recommendations;
- business prioritization.

## 3. Google V1

Google is the first connector. Reuse validated provider implementations from `google-keyword-research` where practical.

Initial capabilities:

- Google Suggest / autocomplete.
- Google Trends exploration.
- Google Trends timeline.
- Related queries where available.

The connector should expose these as source capabilities while returning the common `DemandSignal` model.

## 4. Future connectors

### YouTube
Potential signals:

- search suggestions;
- video titles/descriptions;
- engagement indicators where legally and technically available;
- recurring problem language in public discussions.

### GitHub
Potential signals:

- repository topics/names;
- issues;
- discussions;
- feature requests;
- stars/forks/activity as contextual evidence.

### Reddit
Potential signals:

- posts;
- comments;
- recurring questions;
- complaints and solution-seeking language.

### Hacker News / Product Hunt
Potential signals:

- product launches;
- comments;
- requests and complaints;
- engagement as contextual validation.

## 5. Data-source rules

1. Follow each source's terms, robots/access rules and applicable law.
2. Do not bypass authentication, access controls or anti-abuse mechanisms.
3. Store only the data necessary for the product purpose.
4. Keep collection timestamps and source URLs/identifiers when available.
5. Do not represent estimated or inferred metrics as official source metrics.

## 6. V1 vertical slice

Only Google is required before the first production acceptance. Additional connectors should be added only after the common signal contract and persistence behavior are stable.
