# 03 — Data Model

## 1. Core entities

### ResearchProject
Represents a user-defined research task.

Suggested fields:

- `id` UUID
- `name`
- `seed_query`
- `country`
- `language`
- `source_config` JSONB
- `status`
- `created_at`
- `updated_at`

### ResearchJob
Represents one execution of a research project.

- `id` UUID
- `research_project_id`
- `status`
- `started_at`
- `finished_at`
- `error_code`
- `error_message`
- `stats` JSONB

### DemandSignal
The canonical evidence unit.

- `id` UUID
- `source`
- `source_type`
- `research_job_id`
- `external_id` nullable
- `keyword` nullable
- `normalized_keyword` nullable
- `title` nullable
- `content` nullable
- `url` nullable
- `language` nullable
- `country` nullable
- `occurred_at` nullable
- `collected_at`
- `metrics` JSONB
- `raw_data` JSONB
- `normalized_text`
- `fingerprint` unique
- `confidence`
- `created_at`
- `updated_at`

### Demand
Represents a clustered user need.

- `id`
- `canonical_need`
- `summary`
- `language`
- `country`
- `cluster_method`
- `cluster_confidence`
- `created_at`
- `updated_at`

### DemandSignalMembership
Links signals to a demand cluster.

- `demand_id`
- `signal_id`
- `similarity`
- `membership_reason`

### Opportunity
Represents a productizable demand.

- `id`
- `demand_id`
- `title`
- `problem_statement`
- `target_user`
- `proposed_solution`
- `mvp_scope`
- `competition_summary`
- `monetization_hypothesis`
- `buildability_summary`
- `risks`
- `status`
- `created_at`
- `updated_at`

### OpportunityScore
Stores a transparent score snapshot.

- `id`
- `opportunity_id`
- `total_score`
- `demand_strength`
- `growth_trend`
- `cross_source_validation`
- `competition`
- `build_difficulty`
- `willingness_to_pay`
- `monetization_potential`
- `model_version`
- `created_at`

### ScoreEvidence
Links each score component to evidence or an explicit hypothesis.

- `id`
- `opportunity_score_id`
- `dimension`
- `signal_id` nullable
- `evidence_text`
- `evidence_type` (`source_fact`, `derived_metric`, `ai_hypothesis`, `missing_data`)
- `weight`
- `created_at`

## 2. Fingerprinting

For suggestion-like signals:

`SHA256(source | source_type | country | language | normalized_keyword)`

For time-varying trend signals, include the source date bucket or external time key.

## 3. JSONB policy

JSONB is allowed for source-specific metrics and raw payloads. Fields used for filtering, joining or scoring must be promoted to typed columns when the schema stabilizes.

## 4. Migration policy

Preserve reusable legacy tables where migration is safe. Do not perform destructive migration in the bootstrap phase. Existing legacy tables `research_project`, `research_job` and `keyword` can be retained while `research_keyword` and `keyword_metric_snapshot` are treated as legacy compatibility structures until their replacement is accepted.
