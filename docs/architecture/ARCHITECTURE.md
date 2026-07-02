# ARCHITECTURE.md

# AI-Powered Review Discovery Engine — Master Architecture

**Version:** 1.0
**Status:** Draft
**Owner:** Growth Product Team

---

## System Purpose

Transform large-scale, unstructured customer feedback from public platforms into structured, evidence-backed product intelligence that Product Managers can query in minutes.

The system is a Voice of Customer platform — not a review summarizer.

---

## Architecture Philosophy

Every architectural decision follows six guiding principles from the Problem Statement:

| Principle | Architecture Implication |
|---|---|
| Evidence Over Opinion | Every insight traces to source reviews |
| Structure Before Summaries | Structured schemas defined before LLM calls |
| Explainability | Confidence scores and evidence links on all outputs |
| Human-in-the-Loop | System surfaces findings; humans decide |
| Modularity | Each phase is independently deployable |
| Deterministic Where Possible | AI reserved for semantic tasks; logic handled in code |

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    EXTERNAL DATA SOURCES                        │
│  Apple App Store │ Google Play │ Reddit │ Community │ Social     │
└──────────────────────────┬──────────────────────────────────────┘
                           │ Raw Reviews
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│              PHASE 1 — DATA INGESTION                           │
│  Source Connectors → Raw Validation → Raw Storage               │
└──────────────────────────┬──────────────────────────────────────┘
                           │ RawReview[]
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│              PHASE 2 — PREPROCESSING                            │
│  Cleaning → Language Detection → Deduplication → Normalization  │
└──────────────────────────┬──────────────────────────────────────┘
                           │ NormalizedReview[]
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│              PHASE 3 — AI ANALYSIS (Per Review)                 │
│  LLM Extraction → Metadata Generation → Confidence Scoring      │
└──────────────────────────┬──────────────────────────────────────┘
                           │ AnalyzedReview[]
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│              PHASE 4 — CLUSTERING & PATTERN RECOGNITION         │
│  Embeddings → Semantic Clustering → Theme Labeling → Trends     │
└──────────────────────────┬──────────────────────────────────────┘
                           │ ReviewCluster[]
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│              PHASE 5 — INSIGHT GENERATION                       │
│  JTBD Inference → Segment Detection → Opportunity Scoring       │
└──────────────────────────┬──────────────────────────────────────┘
                           │ ProductInsight[]
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│              PHASE 6 — STORAGE & KNOWLEDGE BASE                 │
│  Structured DB → Vector Store → Evidence Index → Lineage        │
└──────────────────────────┬──────────────────────────────────────┘
                           │ Queryable Knowledge Base
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│              PHASE 7 — QUERY & REPORTING                        │
│  NL Query Engine → Dashboards → Reports → Evidence Viewer       │
└─────────────────────────────────────────────────────────────────┘
```

---

## Phase Summary

| Phase | Name | Primary Input | Primary Output | AI? |
|---|---|---|---|---|
| 1 | Data Ingestion | Public URLs / APIs | RawReview[] | No |
| 2 | Preprocessing | RawReview[] | NormalizedReview[] | No |
| 3 | AI Analysis | NormalizedReview[] | AnalyzedReview[] | Yes |
| 4 | Clustering | AnalyzedReview[] | ReviewCluster[] | Yes |
| 5 | Insight Generation | ReviewCluster[] | ProductInsight[] | Yes |
| 6 | Storage | All above | Queryable Knowledge Base | No |
| 7 | Query & Reporting | Knowledge Base | PM-facing outputs | Yes |

---

## Phase-by-Phase Architecture

---

### Phase 1 — Data Ingestion

**Purpose:** Pull raw reviews from public platforms and store them immutably.

**Components:** Source Connectors → Raw Validator → Raw Storage

**Scale Assumptions:**
- Baseline: up to 50,000 reviews per ingestion batch across all sources.
- Each source connector runs independently; failure of one source does not block others.
- Ingestion is append-only. Re-runs produce new batches, not overwrites.
- Scale trigger: if daily review volume exceeds 200K, connectors move to async queue workers.

**Data Privacy / PII Posture:**
- Only publicly available review content is ingested. No login, scraping of private data, or access beyond public APIs.
- `author_id` is stored as a platform-issued pseudonym (e.g., App Store reviewer alias), never linked to a real identity.
- No email addresses, device identifiers, or demographic data are collected at this phase.
- Platform Terms of Service compliance is the responsibility of the connector for each source.

**Error Recovery & PM Impact:**
- If a source connector fails mid-batch, the batch is marked `PARTIAL` and logged with `source`, `records_fetched`, and `failure_reason`.
- Partial batches are retried on the next scheduled run; already-ingested records are not re-fetched (deduplication in Phase 2 catches any overlap).
- PM impact: a failed connector delays freshness of that source's reviews. Freshness lag is surfaced as a data health indicator in Phase 7 dashboards.

---

### Phase 2 — Preprocessing

**Purpose:** Clean, normalize, deduplicate, and quality-score raw reviews before AI processing.

**Components:** Text Cleaner → Language Detector → Deduplicator → Quality Scorer → Normalizer

**Scale Assumptions:**
- Designed to process 50,000 reviews in under 10 minutes on a single machine (no GPU required).
- Deduplication uses content hashing (SHA-256 of normalized text) — O(n) regardless of corpus size.
- Language detection is a lightweight local model (no API cost).
- Scale trigger: if corpus exceeds 1M total reviews, deduplication moves to a bloom filter.

**Data Privacy / PII Posture:**
- Text cleaning strips URLs, email patterns, and phone number patterns from `clean_text` before any downstream processing.
- Original `raw_text` is preserved immutably in Phase 1 storage but is not forwarded to AI phases.
- Only `clean_text` (sanitized) propagates to Phase 3 and beyond.
- Reviews with `quality_score < 0.2` (e.g., single-word, spam-pattern, or non-language content) are flagged `is_low_quality = true` and excluded from AI analysis.

**Error Recovery & PM Impact:**
- Low-quality reviews are never deleted — they remain in storage with a `skip_reason` field.
- If language detection confidence is below threshold, the review is tagged `language = "unknown"` and excluded from analysis rather than processed incorrectly.
- PM impact: quality filtering reduces noise in downstream insights. The quality report shows what percentage of reviews were excluded and why, so PMs can audit the filter thresholds.

---

### Phase 3 — AI Analysis (Per Review)

**Purpose:** Extract structured signals from each normalized review using an LLM.

**Components:** Prompt Builder → LLM Caller → Response Validator → Confidence Scorer

**Scale Assumptions:**
- Target throughput: 500 reviews per minute using batched async LLM calls.
- Each review costs approximately one LLM API call. At 50K reviews, this is roughly 50K tokens input (assuming ~500 tokens average per review with prompt overhead) — budget this explicitly per run.
- Rate limiting: the LLM caller respects provider rate limits with exponential backoff. No review is skipped due to rate limits; it waits and retries.
- Scale trigger: if per-run review volume exceeds 100K, Phase 3 moves to a worker pool with parallel async execution.

**Data Privacy / PII Posture:**
- Only `clean_text` (PII-stripped by Phase 2) is sent to the LLM API.
- No `author_id`, no platform username, no personal identifiers are included in any LLM prompt.
- LLM provider data handling policy applies: use a provider with a no-training-on-API-data guarantee (Anthropic Claude API meets this requirement).
- Prompt templates are versioned and reviewed before deployment. No freeform user-controlled text is injected into prompts.

**Error Recovery & PM Impact:**
- If the LLM returns a malformed response, the review is marked `analysis_status = "failed"` and queued for retry (up to 3 attempts).
- If all retries fail, the review is excluded from clustering with `skip_reason = "llm_failure"` logged.
- Reviews with `confidence_score < 0.5` are flagged `low_confidence = true`. They are included in clustering but weighted lower in insight generation.
- PM impact: the Phase 3 quality report shows failure rate and confidence distribution. If failure rate exceeds 5%, the pipeline pauses and alerts before Phase 4 begins.

---

### Phase 4 — Clustering & Pattern Recognition

**Purpose:** Group analyzed reviews into semantic themes using embeddings and density-based clustering.

**Components:** Embedding Generator → Vector Indexer → HDBSCAN Clusterer → Theme Labeler → Trend Detector

**Scale Assumptions:**
- Embeddings are generated locally using `sentence-transformers` — no API cost, no external data transfer.
- HDBSCAN clustering runs in memory. Scales to ~500K reviews on a standard machine (16GB RAM).
- Clustering is re-run on each new batch. Existing cluster IDs may shift between runs; `member_review_ids` is the stable reference, not cluster ID.
- Scale trigger: if corpus exceeds 500K reviews, switch to approximate nearest-neighbor indexing (FAISS) to maintain sub-minute clustering time.

**Data Privacy / PII Posture:**
- Embeddings are dense numeric vectors — they do not contain recoverable review text. They are safe to store and query without PII risk.
- Theme labels are generated by the LLM from aggregated cluster summaries, not from individual review text — reducing exposure of any single user's content.
- Cluster members are referenced by `review_id` only; no author information propagates to this phase.

**Error Recovery & PM Impact:**
- HDBSCAN assigns some reviews to a noise cluster (label `-1`). Noise reviews are not discarded — they are stored with `cluster_id = null` and available for manual inspection.
- If a cluster contains fewer than 5 reviews, it is flagged `is_micro_cluster = true` and excluded from insight generation (too small to be statistically meaningful).
- PM impact: micro-clusters and noise are surfaced in the Phase 4 quality report. A rising noise rate signals that review language is diversifying — potentially a new user segment emerging.

---

### Phase 5 — Insight Generation

**Purpose:** Synthesize clusters into PM-actionable insights: JTBDs, problems, opportunities, and unmet needs.

**Components:** JTBD Inferencer → Segment Detector → Opportunity Scorer → Insight Validator

**Scale Assumptions:**
- Insight generation runs on clusters, not individual reviews — input size is bounded by cluster count (typically 20–200 clusters), not review count.
- One LLM call per cluster for JTBD and opportunity inference. At 200 clusters, this is ~200 LLM calls per run — low cost.
- Insights are generated incrementally: only clusters that changed since the last run trigger new insight generation.
- Scale trigger: none required at current design scope. Insight count is naturally bounded.

**Data Privacy / PII Posture:**
- Insights are aggregate outputs. No individual review text, no author identifiers, and no personal signals appear in `ProductInsight` outputs.
- LLM prompts for insight generation use cluster summaries and statistical signals only — not raw review text.
- `supporting_review_ids` are stored as internal UUIDs for lineage tracing. They are not exposed in PM-facing reports unless the PM explicitly drills into evidence.

**Error Recovery & PM Impact:**
- Insights with `confidence_score < 0.6` are generated but tagged `review_required = true`. They appear in a separate "Pending Review" queue in the dashboard, not in the main insight feed.
- If a cluster produces no coherent JTBD signal, it is logged as `no_insight_generated` with a reason code. PMs can inspect these manually.
- PM impact: the confidence threshold is a tunable product parameter. Setting it lower surfaces more insights with more noise; higher means fewer but more reliable insights. Default is `0.6`.

---

### Phase 6 — Storage & Knowledge Base

**Purpose:** Persist all pipeline outputs in queryable, lineage-preserving storage layers.

**Components:** Structured DB (SQLite → PostgreSQL) · Vector Store (ChromaDB) · Evidence Index · Lineage Graph

**Scale Assumptions:**
- SQLite is the default for up to 100K reviews and 5 concurrent users. No infrastructure required.
- Migration trigger to PostgreSQL: review corpus exceeds 100K OR concurrent dashboard users exceed 5. Migration is non-breaking — schemas are identical.
- ChromaDB stores embeddings locally. Scales to ~1M vectors before requiring a managed vector DB.
- All storage is append-only for raw and normalized layers. Analyzed and insight layers support versioned updates.

**Data Privacy / PII Posture:**
- Raw review storage (Phase 1 outputs) is the only layer containing potentially identifiable content (`author_id`, `source_url`). Access to this layer is restricted to the ingestion pipeline.
- PM-facing query interfaces (Phase 7) do not expose raw review author information by default.
- Data retention policy: raw reviews are retained for 24 months. Derived outputs (clusters, insights) are retained indefinitely.
- If a source platform issues a data deletion request (e.g., GDPR takedown), the affected `RawReview` is soft-deleted and all derived objects referencing it are re-flagged. The lineage chain makes this traceable.

**Error Recovery & PM Impact:**
- All writes are transactional. A failed batch write rolls back entirely — no partial states.
- Each pipeline run writes a `pipeline_run` record with status, phase completion flags, and record counts. PMs can see which runs succeeded, which failed, and at what phase.
- PM impact: storage failures surface immediately in the pipeline run log. The dashboard shows a "data freshness" timestamp so PMs know when the knowledge base was last successfully updated.

---

### Phase 7 — Query & Reporting

**Purpose:** Expose the knowledge base to PMs through natural language queries, dashboards, and evidence-linked reports.

**Components:** NL Query Engine · Insight Dashboard · Evidence Viewer · Report Exporter

**Scale Assumptions:**
- Designed for 1–10 concurrent PM users in the initial deployment. No multi-tenancy required at this stage.
- Query response time target: under 3 seconds for structured queries; under 10 seconds for NL queries involving LLM interpretation.
- Scale trigger: if concurrent users exceed 10 or query latency exceeds targets, introduce query result caching (Redis or in-memory) for common queries.

**Data Privacy / PII Posture:**
- PM-facing dashboards display aggregated insights and cluster-level data by default. Individual reviews are only accessible through the Evidence Viewer, which requires explicit drill-down action.
- The Evidence Viewer shows `clean_text` (PII-stripped) and `platform`, never `author_id` or `source_url`.
- Report exports (PDF/CSV) include only aggregated data unless the PM explicitly requests raw evidence, which triggers an audit log entry.
- Access to the dashboard is role-gated. PMs see insights; only data owners can access raw review storage.

**Error Recovery & PM Impact:**
- If the underlying knowledge base has not been updated within 48 hours, the dashboard displays a visible "Data Stale" warning with the last successful update timestamp.
- NL query failures (LLM unable to interpret query) return a plain-language error message with suggested query rephrasing — not a blank result.
- If a PM queries a time range with no data, the system returns "No reviews ingested for this period" rather than empty charts.
- PM impact: the system never silently returns empty or misleading results. Every no-data state is explicitly labeled.

---

## Data Lineage Contract

Every data object carries forward a traceable lineage chain:

```
RawReview.id
  └── NormalizedReview.source_review_id
        └── AnalyzedReview.normalized_review_id
              └── ReviewCluster.member_review_ids[]
                    └── ProductInsight.supporting_cluster_ids[]
                          └── Report.evidence_trace[]
```

This lineage is non-negotiable. Breaking it is an architecture violation.

---

## Core Data Models

### RawReview
```json
{
  "id": "uuid",
  "source_platform": "app_store | google_play | reddit | community | social",
  "raw_text": "string",
  "rating": "1-5 | null",
  "author_id": "string | null",
  "published_at": "ISO8601",
  "source_url": "string",
  "ingested_at": "ISO8601",
  "ingestion_batch_id": "string"
}
```

### NormalizedReview
```json
{
  "id": "uuid",
  "source_review_id": "uuid",
  "clean_text": "string",
  "normalized_rating": "1.0-5.0 | null",
  "language": "string",
  "word_count": "integer",
  "quality_score": "0.0-1.0",
  "is_duplicate": "boolean",
  "duplicate_of_id": "uuid | null",
  "platform": "string",
  "normalized_at": "ISO8601"
}
```

### AnalyzedReview
```json
{
  "id": "uuid",
  "normalized_review_id": "uuid",
  "sentiment": "positive | negative | neutral | mixed",
  "sentiment_score": "-1.0 to 1.0",
  "discovery_friction_detected": "boolean",
  "primary_complaint": "string | null",
  "primary_praise": "string | null",
  "feature_mentions": ["string"],
  "jtbd_signal": "string | null",
  "user_intent": "string | null",
  "root_cause_signal": "string | null",
  "user_segment_signal": "power_user | casual | new | churned | unknown",
  "emotion_tags": ["frustration | delight | confusion | boredom"],
  "confidence_score": "0.0-1.0",
  "analysis_model": "string",
  "analyzed_at": "ISO8601"
}
```

### ReviewCluster
```json
{
  "id": "uuid",
  "label": "string",
  "theme": "string",
  "member_review_ids": ["uuid"],
  "centroid_embedding": "float[]",
  "size": "integer",
  "avg_sentiment_score": "float",
  "discovery_friction_rate": "0.0-1.0",
  "dominant_platform": "string",
  "trend_direction": "increasing | stable | decreasing",
  "created_at": "ISO8601"
}
```

### ProductInsight
```json
{
  "id": "uuid",
  "title": "string",
  "description": "string",
  "insight_type": "jtbd | problem | opportunity | unmet_need | segment",
  "supporting_cluster_ids": ["uuid"],
  "supporting_review_ids": ["uuid"],
  "affected_segment": "string",
  "severity_score": "0.0-1.0",
  "frequency_score": "0.0-1.0",
  "opportunity_score": "0.0-1.0",
  "confidence": "high | medium | low",
  "confidence_score": "0.0-1.0",
  "review_required": "boolean",
  "reasoning": "string",
  "generated_at": "ISO8601"
}
```

---

## Technology Stack (Recommended)

| Layer | Technology | Rationale |
|---|---|---|
| Language | Python 3.11+ | Ecosystem for AI/ML and data processing |
| LLM Provider | Anthropic Claude | Structured output, high reasoning quality, no-training-on-API-data policy |
| Embeddings | sentence-transformers | Local, fast, no API cost, no data leaves the machine |
| Vector DB | ChromaDB | Lightweight, local-first, embeddable |
| Structured DB | SQLite → PostgreSQL | Start simple, migrate when needed (trigger: >100K reviews or >5 users) |
| Clustering | HDBSCAN | Handles noise, variable cluster sizes |
| Orchestration | Python scripts → Prefect | Start simple, graduate to orchestration |
| Dashboards | Streamlit | Rapid PM-facing UI, no frontend needed |
| Testing | pytest | Standard Python testing |

---

## Architectural Constraints

1. Raw data is **immutable** — never modify after ingestion.
2. Every AI call must produce structured JSON output, not free text.
3. Every insight must carry `confidence_score` and `supporting_review_ids`.
4. Phases communicate through well-defined data contracts.
5. Each phase must be runnable independently for debugging.
6. No phase may read from another phase's internal state — only published outputs.
7. Only `clean_text` (PII-stripped) propagates beyond Phase 2. Raw text never reaches AI phases.
8. No `author_id` or personal identifier may appear in any LLM prompt or PM-facing output.
9. Every pipeline run produces a `pipeline_run` record with phase-level status. Silent failures are an architecture violation.

---

## Directory Structure

```
spotify-review-discovery-engine/
├── docs/
│   ├── architecture/           ← Master + per-phase architecture docs
│   ├── skills/                 ← Engineering skills reference
│   └── problemStatement.md
├── phase-1-data-ingestion/     ← Source connectors and raw storage
├── phase-2-preprocessing/      ← Cleaning, normalization, deduplication
├── phase-3-ai-analysis/        ← Per-review LLM analysis
├── phase-4-clustering/         ← Embeddings and semantic clustering
├── phase-5-insight-generation/ ← JTBD, opportunities, segments
├── phase-6-storage/            ← All persistence layers
└── phase-7-query-reporting/    ← Dashboards, reports, NL query
```

---

## Cross-Cutting Concerns

### Observability
Every phase emits structured logs with:
- `phase`, `batch_id`, `record_count`, `duration_ms`, `error_count`

### Error Handling
- Each phase produces a `quality_report.json` summarizing failures, skips, and confidence distributions.
- No phase silently swallows errors.
- Pipeline halts and alerts if any phase error rate exceeds 5%.

### Data Privacy
- PII sanitization is enforced at Phase 2 before any AI processing.
- The LLM provider (Anthropic) does not train on API-submitted data.
- Raw review author data is access-restricted; PM-facing layers expose only aggregated signals.
- GDPR-style deletion requests are traceable via the lineage chain.

### Scalability Thresholds

| Threshold | Trigger Action |
|---|---|
| > 100K reviews | Migrate SQLite → PostgreSQL |
| > 200K reviews/day | Move ingestion connectors to async queue workers |
| > 500K embeddings | Switch to FAISS approximate nearest-neighbor indexing |
| > 5 concurrent PM users | Introduce query result caching |

### Versioning
- Schemas are versioned (`schema_version` field on all models).
- Prompts are versioned (`prompt_version` field on all AI outputs).
- Breaking schema changes require migration scripts.
