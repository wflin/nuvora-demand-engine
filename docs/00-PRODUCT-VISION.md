# 00 — Product Vision

## 1. Product definition

Nuvora Demand Engine is the internal demand intelligence platform used to answer one business question:

> **What should Nuvora build next, for whom, and why?**

The system continuously collects public demand signals, groups related signals into user needs, evaluates product opportunities, and produces evidence-backed recommendations for MVP development.

## 2. Business goal

Nuvora is intended to operate a repeatable product factory rather than rely on occasional ideas. The engine therefore optimizes for a repeatable loop:

1. Discover demand.
2. Validate demand.
3. Select an opportunity.
4. Define a small MVP.
5. Build quickly with Codex.
6. Launch internationally.
7. Measure real user behavior and revenue.
8. Feed results back into discovery.

## 3. Product principles

### Evidence before opinion
Every material recommendation must be supported by observable evidence. AI may interpret evidence, but it must not fabricate demand, traffic, volume, pricing, competitors or user intent.

### Multi-source confirmation
A signal from one source is useful; corroboration across independent sources is stronger. The system should preserve source-level evidence and distinguish direct evidence from AI inference.

### Buildability matters
A large demand signal is not automatically a good Nuvora opportunity. The ranking must account for MVP complexity, dependencies, data access, operational burden and expected time-to-market.

### Monetization matters
The engine should identify plausible ways to charge users and the strength of the available willingness-to-pay evidence.

### Freshness matters
A 2026 signal and a five-year-old signal must not be treated as equivalent. Every signal carries collection and occurrence timestamps where available.

### Transparent scoring
The score is a decision aid, not a black box. Users must be able to inspect the evidence behind each major score component.

## 4. Key concepts

- **DemandSignal**: an individual piece of evidence collected from a source.
- **Demand**: a normalized user need formed by clustering related signals.
- **Opportunity**: a productizable demand with a target user, problem, evidence, competitive context, buildability and monetization hypothesis.
- **OpportunityScore**: a transparent weighted evaluation of an opportunity.
- **Recommendation**: the final action-oriented output, including why the opportunity is worth validating and what MVP to test.

## 5. V1 scope

V1 must prove one complete vertical slice using Google-derived signals:

`Research input → Google collection → normalized DemandSignal → persistence → analysis-ready data → opportunity candidate → transparent score → API result`

V1 should not attempt to fully automate product development or support every source immediately.

## 6. Future scope

After the first vertical slice is stable, add source connectors incrementally:

- YouTube
- GitHub
- Reddit
- Hacker News
- Product Hunt
- App stores
- Additional search/discussion/review sources

The common contract remains `DemandSignal` so the analysis and scoring layers do not depend on source-specific schemas.
