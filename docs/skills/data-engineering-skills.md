# Data Engineering Skills

**Version:** 1.0
**Purpose:** Design, build, and maintain reliable, scalable, and traceable data pipelines for AI-powered customer feedback analysis.

**Applies To:**

* App Store Reviews
* Google Play Reviews
* Community Forums
* Reddit
* X (Twitter)
* Support Tickets
* Survey Responses
* Internal Product Feedback

---

# Mission

Your responsibility is **not** to collect data.

Your responsibility is to build trustworthy data foundations that enable reliable AI reasoning and product decision-making.

Every downstream insight depends on upstream data quality.

Bad data cannot be corrected by better prompts.

---

# Data Engineering Philosophy

Data is a product.

Treat every dataset as a long-lived product with:

* Owners
* Contracts
* Versioning
* Quality metrics
* Documentation
* Monitoring
* Consumers

Optimize for reliability before scale.

---

# Guiding Principles

Every data pipeline should be:

* Reliable
* Repeatable
* Observable
* Traceable
* Incremental
* Idempotent
* Schema-driven
* Source-aware

Every transformation should be reproducible.

---

# Data Lifecycle

```text
Source Systems
        ↓
Ingestion
        ↓
Raw Storage
        ↓
Normalization
        ↓
Validation
        ↓
Enrichment
        ↓
Canonical Dataset
        ↓
AI Processing
        ↓
Insights
        ↓
Dashboards
```

Never overwrite raw data.

Raw data is immutable.

---

# Supported Data Sources

Design connectors independently.

Examples:

* Apple App Store
* Google Play Store
* Spotify Community
* Reddit
* X
* YouTube comments
* Trustpilot
* Internal CRM exports
* Customer surveys

Each connector should implement the same interface.

Never hardcode source-specific logic into downstream processing.

---

# Canonical Data Model

Normalize every source into a shared schema.

Required fields:

```json
{
  "review_id": "",
  "source": "",
  "platform": "",
  "author": "",
  "timestamp": "",
  "language": "",
  "rating": null,
  "title": "",
  "body": "",
  "url": "",
  "metadata": {}
}
```

Downstream AI should consume only canonical records.

---

# Data Contracts

Every pipeline stage must define:

* Expected inputs
* Output schema
* Required fields
* Validation rules
* Failure behavior

Changes require version updates.

Treat schemas as APIs.

---

# Raw Zone

Store original records exactly as received.

Characteristics:

* Immutable
* Append-only
* Source-specific
* Auditable

Never clean or modify raw data.

This layer is the source of truth.

---

# Normalized Zone

Transform raw data into canonical records.

Operations include:

* Encoding normalization
* Timestamp normalization
* Language detection
* Rating normalization
* Text extraction
* Metadata mapping

Avoid business logic at this stage.

---

# Enriched Zone

Augment records with derived metadata.

Examples:

* Language confidence
* Token count
* Duplicate score
* Source reliability
* Review age
* Geographic hints
* Platform category

Derived fields should remain distinguishable from source fields.

---

# AI Feature Store

Store reusable AI outputs separately.

Examples:

* Embeddings
* Sentiment
* JTBD
* User segment
* Theme labels
* Recommendation issues
* Root causes

Do not recompute unchanged AI features.

Cache intelligently.

---

# Incremental Ingestion

Pipelines should ingest only new or changed records.

Track:

* Last processed timestamp
* Cursor
* Review ID
* Source checkpoint

Avoid full reprocessing whenever possible.

---

# Idempotency

Running the same ingestion twice should produce identical results.

Prevent:

* Duplicate reviews
* Duplicate embeddings
* Duplicate AI analyses

Every record must have a stable unique identifier.

---

# Deduplication Strategy

Duplicates may exist:

* Across platforms
* Across exports
* Within the same source

Use multiple signals:

* Review ID
* Text similarity
* Author
* Timestamp
* Semantic similarity

Flag duplicates rather than deleting immediately.

---

# Data Quality Framework

Measure:

* Completeness
* Accuracy
* Consistency
* Validity
* Uniqueness
* Timeliness

Every pipeline run should produce a quality report.

---

# Validation Rules

Validate:

* Required fields
* Character encoding
* Language
* Timestamp
* Rating range
* Source identifiers

Reject malformed records gracefully.

Do not terminate the entire pipeline due to isolated failures.

---

# Metadata Enrichment

Capture operational metadata.

Examples:

```text
Pipeline Version
Ingestion Timestamp
Source Connector
Transformation Version
Schema Version
Processing Duration
```

Operational metadata improves debugging and traceability.

---

# Data Lineage

Every derived insight must be traceable back to:

Insight

↓

Cluster

↓

Structured Review

↓

Canonical Record

↓

Raw Source

Maintain lineage across all pipeline stages.

---

# Storage Layers

Organize storage by responsibility.

```text
/raw
    ↓
/normalized
    ↓
/enriched
    ↓
/features
    ↓
/analytics
```

Avoid mixing responsibilities within a single dataset.

---

# Dataset Versioning

Version datasets whenever:

* Schema changes
* Taxonomies change
* AI outputs change
* Business logic changes

Record:

* Version
* Date
* Reason
* Backward compatibility

---

# Batch vs Incremental Processing

Use batch processing for:

* Historical imports
* Backfills
* Model retraining

Use incremental processing for:

* Daily ingestion
* Scheduled updates
* Near-real-time dashboards

Choose the simplest architecture that meets business needs.

---

# Privacy by Design

Do not retain unnecessary personal information.

Prefer:

* Pseudonymized identifiers
* Minimal metadata
* Data retention policies

Respect platform terms of service and applicable regulations.

---

# Observability

Monitor:

* Pipeline success rate
* Failed records
* Ingestion latency
* Throughput
* Duplicate rate
* Quality score
* Processing cost

Expose metrics through dashboards.

---

# Error Handling

Handle failures gracefully.

Common scenarios:

* API rate limits
* Connector failures
* Invalid JSON
* Missing fields
* Network interruptions
* Partial imports

Retry where appropriate.

Log failures with actionable diagnostics.

---

# Scalability

Design pipelines that scale independently.

Separate:

* Connectors
* Transformations
* AI processing
* Analytics

Avoid tightly coupled workflows.

---

# Repository Organization

Recommended structure:

```text
data/
├── raw/
├── normalized/
├── enriched/
├── features/
├── analytics/
└── evaluation/

schemas/
├── canonical-review.schema.json
├── enrichment.schema.json
├── insight.schema.json
└── metrics.schema.json

pipelines/
├── ingest/
├── normalize/
├── enrich/
├── feature_generation/
└── export/
```

Keep schemas, pipelines, and datasets independent.

---

# Data Quality Checklist

Before releasing a dataset verify:

* Schema validated
* Required fields populated
* Duplicates identified
* Metadata complete
* Lineage preserved
* Version recorded
* Quality metrics generated
* Documentation updated

---

# Common Anti-Patterns

Avoid:

* Overwriting raw data
* Mixing source-specific logic into analytics
* Hardcoding schemas
* Reprocessing all data unnecessarily
* Ignoring duplicates
* Losing lineage
* Storing AI outputs inside raw datasets
* Silent data corruption
* Unversioned datasets

---

# Definition of Done

A data pipeline is complete only when:

* Source connectors are modular.
* Raw data is immutable.
* Canonical schemas are enforced.
* Validation passes.
* Lineage is preserved.
* Incremental processing is supported.
* AI feature generation is reusable.
* Quality metrics are reported.
* Documentation is synchronized.
* Downstream AI systems can consume the data without source-specific logic.

---

# Guiding Principle

> **Data engineering is not about moving records from one system to another. It is about creating trustworthy, versioned, and observable datasets that allow AI systems to generate reliable product intelligence. Every insight is only as good as the data contract beneath it.**
