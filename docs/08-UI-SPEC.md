# 08 — UI Specification

The frontend is not required for the first backend vertical slice. When implemented, it should expose the evidence chain rather than only a score table.

## 1. Research page

Inputs:

- seed topic/keyword;
- country;
- language;
- sources;
- optional time range.

Actions:

- Start research.
- View previous runs.

## 2. Research run page

Show:

- run status;
- sources executed;
- signals collected;
- errors/warnings;
- timestamp;
- data freshness.

## 3. Opportunity list

Columns/cards:

- opportunity name;
- total score;
- confidence;
- demand strength;
- growth;
- competition;
- build difficulty;
- monetization;
- evidence count;
- freshness.

Filters should allow the user to narrow by market, source, score and lifecycle state.

## 4. Opportunity detail

The most important screen.

Sections:

1. Executive recommendation.
2. Problem and target user.
3. Score breakdown.
4. Evidence timeline.
5. Cross-source validation.
6. Existing competitors.
7. MVP proposal.
8. Monetization hypothesis.
9. Risks.
10. Recommended validation experiment.

The UI must distinguish source facts from AI hypotheses visually and semantically.

## 5. Design principle

The system should answer “why should I build this?” before “what is the score?”.
