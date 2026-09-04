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
