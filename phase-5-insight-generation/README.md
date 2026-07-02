# Phase 5 — Insight Generation

## Objective

Convert clusters of related reviews into actionable, evidence-backed product intelligence: Jobs To Be Done, user segments, unmet needs, and scored product opportunities.

This is the core intelligence layer of the system — where patterns become product knowledge.

---

## Responsibilities

- Infer Jobs To Be Done (JTBD) from cluster patterns
- Detect and characterize user segments from behavioral signals
- Identify unmet needs not addressed by current features
- Score product opportunities by frequency, severity, and uniqueness
- Map all insights to supporting clusters and reviews (evidence trail)
- Assign confidence levels to every output

---

## Non-Responsibilities

- Generating dashboards or reports (Phase 7)
- Storing results permanently (Phase 6)
- Clustering reviews (Phase 4)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│         INPUT: ReviewCluster[] from Phase 4                     │
│         + AnalyzedReview[] from Phase 3 (for cross-reference)   │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│         PARALLEL ANALYSIS PIPELINES                              │
│                                                                  │
│  ┌──────────────────────┐   ┌─────────────────────────────────┐  │
│  │  JTBD INFERENCE      │   │  SEGMENT DETECTION              │  │
│  │                      │   │                                 │  │
│  │  ClusterJTBDInferrer │   │  SegmentProfiler                │  │
│  │  → Per-cluster JTBD  │   │  → Power user profile          │  │
│  │  → Cross-cluster     │   │  → Casual listener profile      │  │
│  │    JTBD synthesis    │   │  → New user profile             │  │
│  └──────────┬───────────┘   │  → Churned user profile        │  │
│             │               └────────────┬────────────────────┘  │
│             └────────────────────┬───────┘                       │
│                                  │                               │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │         UNMET NEEDS ANALYSIS                             │    │
│  │                                                          │    │
│  │  UnmetNeedDetector                                       │    │
│  │  → Reviews expressing desire not fulfilled by product    │    │
│  │  → Gap between "what user wants" and "what exists"       │    │
│  └──────────────────────────────┬───────────────────────────┘    │
│                                 │                                │
└─────────────────────────────────┼────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                   OPPORTUNITY SCORING                           │
│                                                                 │
│  OpportunityScorer                                              │
│  → Combines JTBD + Segments + Unmet Needs                       │
│  → Scores each opportunity on:                                  │
│     Frequency: how many users affected                          │
│     Severity: how strongly users feel about it                  │
│     Uniqueness: how specific/novel the need is                  │
│  → Opportunity Score = freq × severity × (1 + uniqueness)       │
│  → Ranks all opportunities                                      │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                   EVIDENCE MAPPER                               │
│                                                                 │
│  EvidenceMapper                                                 │
│  → Links each insight to:                                       │
│     - supporting_cluster_ids                                    │
│     - supporting_review_ids (sample of 3–10 verbatims)          │
│     - confidence_score                                          │
│     - reasoning (LLM-generated explanation)                     │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│         OUTPUT: ProductInsight[] (JSONL)                        │
│         + insight_quality_report.json                           │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Models

### ProductInsight Schema

```json
{
  "id": "uuid-v4",
  "title": "concise insight title",
  "description": "2-3 sentence description of the insight",
  "insight_type": "jtbd | problem | opportunity | unmet_need | segment",
  "supporting_cluster_ids": ["uuid"],
  "supporting_review_ids": ["uuid — 3–10 representative verbatims"],
  "supporting_verbatims": ["direct quote from review text"],
  "affected_segment": "power_user | casual | new | churned | all",
  "frequency_score": "0.0–1.0 — fraction of total reviews affected",
  "severity_score": "0.0–1.0 — avg emotional intensity of affected reviews",
  "uniqueness_score": "0.0–1.0 — how specific/novel this need is",
  "opportunity_score": "0.0–1.0 — composite prioritization score",
  "confidence": "high | medium | low",
  "confidence_score": "0.0–1.0",
  "reasoning": "explanation of why this insight was generated",
  "discovery_friction_related": "boolean",
  "trend_direction": "increasing | stable | decreasing",
  "generated_at": "ISO8601",
  "generation_model": "string",
  "prompt_version": "string",
  "schema_version": "1.0"
}
```

### JTBDProfile Schema

```json
{
  "id": "uuid-v4",
  "job_statement": "When [situation], I want to [motivation], so I can [outcome]",
  "short_label": "concise JTBD label",
  "supporting_cluster_ids": ["uuid"],
  "user_segments": ["string"],
  "frequency_estimate": "integer — estimated users affected",
  "satisfaction_score": "0.0–1.0 — how well current product satisfies this job",
  "gap_score": "1.0 - satisfaction_score",
  "confidence_score": "0.0–1.0"
}
```

### UserSegment Schema

```json
{
  "id": "uuid-v4",
  "segment_label": "power_user | casual | new | churned | niche_explorer",
  "description": "behavioral characterization of this segment",
  "behavioral_signals": ["string"],
  "primary_jtbd": "string",
  "primary_pain": "string",
  "review_count": "integer",
  "fraction_of_total": "0.0–1.0",
  "discovery_friction_rate": "0.0–1.0",
  "platform_affinity": "string"
}
```

### UnmetNeed Schema

```json
{
  "id": "uuid-v4",
  "need_statement": "Users need [capability] but currently cannot [outcome]",
  "supporting_cluster_ids": ["uuid"],
  "affected_segment": "string",
  "expressed_frequency": "integer",
  "related_features": ["existing Spotify features that partially address this"],
  "gap_description": "what is missing between current state and user need",
  "confidence_score": "0.0–1.0"
}
```

---

## Component Specifications

### ClusterJTBDInferrer

For each discovery-related cluster:
- Sample 10 reviews with `jtbd_signal != null`
- Synthesize a canonical JTBD statement using LLM
- Format: "When [situation], I want to [motivation], so I can [outcome]"
- Evaluate satisfaction: review sentiment avg as proxy

Cross-cluster synthesis:
- Group similar JTBD statements (embedding similarity > 0.8)
- Merge into canonical JTBD profiles
- Aggregate supporting reviews

**JTBD Inference Prompt v1.0:**
```
You are a Jobs To Be Done (JTBD) researcher analyzing Spotify user feedback.

Below are user reviews from a cluster with theme: "{cluster_theme}"

Reviews:
{reviews}

Based on these reviews, identify the primary Job To Be Done using this format:
"When [situation], I want to [motivation], so I can [outcome]"

Also assess:
- How satisfied are users with Spotify's current solution? (0.0–1.0)
- What is the gap between current product and what users need?

Return JSON:
{
  "job_statement": "When ... I want to ... so I can ...",
  "short_label": "3-5 word label",
  "satisfaction_score": 0.0-1.0,
  "gap_description": "string",
  "confidence": 0.0-1.0
}
```

### SegmentProfiler

- Groups AnalyzedReview records by `user_segment_signal`
- For each segment, computes:
  - Discovery friction rate
  - Top complaints (most frequent `primary_complaint` values)
  - Most mentioned features
  - Sentiment distribution
  - Platform affinity
- Generates segment description via LLM

### UnmetNeedDetector

- Filters reviews containing linguistic patterns:
  - "wish", "should", "would be great if", "why can't", "if only", "I want"
  - Combined with negative sentiment and discovery friction
- Groups by cluster
- Synthesizes need statements via LLM
- Scores by expression frequency

### OpportunityScorer

**Scoring Formula:**
```
frequency_score = (cluster.size / total_reviews)
severity_score = abs(cluster.avg_sentiment_score) when negative, else 0
uniqueness_score = 1 - (cluster.size / largest_cluster_size)  [niche = unique]
opportunity_score = (frequency_score * 0.4) + (severity_score * 0.4) + (uniqueness_score * 0.2)
```

**Output:** Ranked list of opportunities sorted by `opportunity_score` descending.

### EvidenceMapper

- For each ProductInsight:
  - Finds 3–10 representative verbatims (reviews closest to cluster centroid)
  - Attaches direct quotes as `supporting_verbatims`
  - Records full review ID chain for traceback to raw data

---

## Directory Structure

```
phase-5-insight-generation/
├── README.md                         ← This file
├── jtbd/
│   ├── __init__.py
│   ├── cluster_jtbd_inferrer.py      ← Per-cluster JTBD extraction
│   ├── jtbd_synthesizer.py           ← Cross-cluster JTBD merging
│   └── prompts/
│       └── jtbd_inference_v1.0.md
├── segments/
│   ├── __init__.py
│   └── segment_profiler.py           ← User segment characterization
├── unmet-needs/
│   ├── __init__.py
│   ├── need_detector.py              ← Pattern-based need extraction
│   └── need_synthesizer.py           ← LLM need statement generation
├── opportunities/
│   ├── __init__.py
│   ├── opportunity_scorer.py         ← Composite scoring logic
│   ├── evidence_mapper.py            ← Review traceability
│   └── opportunity_ranker.py        ← Final ranked list
├── tests/
│   ├── test_jtbd_inferrer.py
│   ├── test_segment_profiler.py
│   ├── test_opportunity_scorer.py
│   └── test_evidence_mapper.py
├── insight_pipeline.py               ← Orchestrates full insight run
└── quality_report.py                 ← Insight quality summary
```

---

## Pipeline Flow

```
1. Load ReviewCluster JSONL from Phase 4
2. Load AnalyzedReview JSONL from Phase 3 (for cross-reference)
3. In parallel:
   a. ClusterJTBDInferrer → per-cluster JTBD
   b. SegmentProfiler → user segment profiles
   c. UnmetNeedDetector → unmet need statements
4. JTBDSynthesizer → merge similar JTBDs across clusters
5. OpportunityScorer → score and rank all opportunities
6. EvidenceMapper → attach verbatims to each insight
7. Write ProductInsight JSONL (JTBD, opportunities, segments, unmet needs)
8. Emit insight_quality_report.json
```

---

## Quality Report Output

```json
{
  "run_date": "ISO8601",
  "total_clusters_analyzed": 34,
  "insights_generated": {
    "jtbd_profiles": 12,
    "opportunities": 28,
    "user_segments": 4,
    "unmet_needs": 16
  },
  "top_opportunity_score": 0.84,
  "avg_confidence_score": 0.73,
  "low_confidence_insights": 5,
  "discovery_related_insights": 19
}
```

---

## Testing Strategy

| Test Type | Coverage |
|---|---|
| Unit | JTBD inferrer produces correctly-formatted job statements |
| Unit | OpportunityScorer produces scores in [0,1] range |
| Unit | EvidenceMapper correctly resolves review IDs to verbatims |
| Unit | UnmetNeedDetector correctly filters linguistic patterns |
| Integration | Full pipeline: clusters → insights with evidence |
| Regression | Known high-priority clusters always score above threshold |

---

## Success Criteria

- Every ProductInsight links to ≥ 3 supporting review IDs
- All opportunity scores are in [0, 1] range
- JTBD statements conform to "When/I want/so I can" format
- No insight has empty `reasoning` field
- `confidence` field is present on every output

---

## Dependencies

- `anthropic` — JTBD inference, segment description, need synthesis
- `numpy` — Opportunity scoring math
- `pydantic` — Schema validation

---

## Phase 5 → Phase 6 Contract

Phase 5 writes JSONL files for: ProductInsight[], JTBDProfile[], UserSegment[], UnmetNeed[].
Phase 6 loads all of these into the structured database and vector store.
