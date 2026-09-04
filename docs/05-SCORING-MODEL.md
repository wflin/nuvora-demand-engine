# 05 — Opportunity Scoring Model

## 1. Purpose

The score ranks opportunities for further validation. It is not a prediction of revenue or success.

## 2. V1 dimensions

| Dimension | Weight | Meaning |
|---|---:|---|
| Demand strength | 25 | Evidence that people actively seek or discuss the need |
| Growth trend | 15 | Evidence that demand is increasing or strengthening |
| Cross-source validation | 15 | Independent sources supporting the same need |
| Competition | 15 | Relative competitive pressure; lower saturation is better |
| Build difficulty | 10 | Expected effort and technical/operational complexity |
| Willingness to pay | 10 | Evidence that users pay or seek paid solutions |
| Monetization potential | 10 | Plausible ability to capture value |
| **Total** | **100** | |

## 3. Scoring rules

Each dimension is normalized to 0–100 before applying its weight.

`total = Σ(dimension_score × weight / 100)`

Scores must store a `model_version` so the same opportunity can be rescored without losing historical results.

## 4. Evidence quality

Evidence types:

- `source_fact`: directly reported by a source;
- `derived_metric`: deterministic calculation from source facts;
- `ai_hypothesis`: model-generated interpretation that requires validation;
- `missing_data`: no reliable evidence available.

A missing metric must not silently become zero or an invented estimate.

## 5. Competition interpretation

Competition is not simply “number of competitors”. The engine should distinguish:

- number of credible alternatives;
- quality/maturity of alternatives;
- pricing;
- review/complaint gaps;
- differentiation opportunities;
- switching friction.

## 6. Confidence

A high opportunity score with weak evidence should remain visibly low-confidence. Recommendation output must show both score and confidence.

## 7. Versioning

Initial model version: `v1.0`.

Changing weights, definitions or normalization rules requires a new model version and should not overwrite historical score snapshots.
