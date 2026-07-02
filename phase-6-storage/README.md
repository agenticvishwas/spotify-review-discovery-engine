# Phase 6 — Storage & Knowledge Base

## Objective

Persist all data from all phases into a queryable, versioned, traceable knowledge base.

This phase is the central data layer that all downstream querying and reporting (Phase 7) reads from.

---

## Responsibilities

- Define and version all database schemas
- Store structured data from all phases in a relational database
- Store embeddings in a vector database for semantic search
- Maintain data lineage from raw reviews to insights
- Provide repository interfaces for all data types
- Support schema migrations

---

## Non-Responsibilities

- Processing or analyzing data (Phases 1–5)
- Querying or reporting (Phase 7)
- Any business logic

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│     INPUT: JSONL files from all phases (1–5)                    │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                   INGESTION LOADER                              │
│                                                                 │
│  PhaseLoader                                                    │
│  → Reads JSONL per phase                                        │
│  → Validates schema_version before writing                      │
│  → Upserts records (idempotent on ID)                           │
└───────────────────────────┬──────────────────────────────────────┘
                            │
           ┌────────────────┼────────────────┐
           │                │                │
           ▼                ▼                ▼
┌──────────────────┐ ┌────────────┐ ┌──────────────────┐
│  STRUCTURED DB   │ │ VECTOR DB  │ │  EVIDENCE INDEX  │
│                  │ │            │ │                  │
│  SQLite (dev)    │ │ ChromaDB   │ │  Flat JSON maps  │
│  PostgreSQL (prod│ │            │ │  review_id →     │
│                  │ │  Collections│ │  cluster_id →   │
│  Tables:         │ │  - reviews  │ │  insight_id      │
│  raw_reviews     │ │  - clusters │ │                  │
│  norm_reviews    │ │  - insights │ │  Used for fast   │
│  analyzed_reviews│ │            │ │  lineage lookups  │
│  clusters        │ │  Enables:  │ │                  │
│  insights        │ │  semantic  │ └──────────────────┘
│  jtbd_profiles   │ │  search    │
│  segments        │ │  on text + │
│  unmet_needs     │ │  insights  │
└──────────────────┘ └────────────┘
```

---

## Database Schema

### Table: raw_reviews

```sql
CREATE TABLE raw_reviews (
    id TEXT PRIMARY KEY,
    source_platform TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    rating INTEGER,
    author_id TEXT,
    published_at TIMESTAMP NOT NULL,
    source_url TEXT,
    ingested_at TIMESTAMP NOT NULL,
    ingestion_batch_id TEXT NOT NULL,
    schema_version TEXT NOT NULL DEFAULT '1.0'
);
```

### Table: normalized_reviews

```sql
CREATE TABLE normalized_reviews (
    id TEXT PRIMARY KEY,
    source_review_id TEXT NOT NULL REFERENCES raw_reviews(id),
    clean_text TEXT NOT NULL,
    normalized_rating REAL,
    language TEXT,
    word_count INTEGER NOT NULL,
    quality_score REAL NOT NULL,
    is_duplicate BOOLEAN NOT NULL DEFAULT FALSE,
    duplicate_of_id TEXT,
    platform TEXT NOT NULL,
    published_at TIMESTAMP,
    normalized_at TIMESTAMP NOT NULL,
    schema_version TEXT NOT NULL DEFAULT '1.0'
);
CREATE INDEX idx_norm_reviews_platform ON normalized_reviews(platform);
CREATE INDEX idx_norm_reviews_quality ON normalized_reviews(quality_score);
```

### Table: analyzed_reviews

```sql
CREATE TABLE analyzed_reviews (
    id TEXT PRIMARY KEY,
    normalized_review_id TEXT NOT NULL REFERENCES normalized_reviews(id),
    source_review_id TEXT NOT NULL,
    sentiment TEXT NOT NULL,
    sentiment_score REAL NOT NULL,
    discovery_friction_detected BOOLEAN NOT NULL,
    discovery_friction_description TEXT,
    primary_complaint TEXT,
    primary_praise TEXT,
    jtbd_signal TEXT,
    user_intent TEXT,
    root_cause_signal TEXT,
    user_segment_signal TEXT,
    emotion_tags TEXT,       -- JSON array stored as string
    feature_mentions TEXT,   -- JSON array stored as string
    listening_behavior_signal TEXT,
    confidence_score REAL NOT NULL,
    analysis_model TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    analyzed_at TIMESTAMP NOT NULL,
    schema_version TEXT NOT NULL DEFAULT '1.0'
);
CREATE INDEX idx_analyzed_friction ON analyzed_reviews(discovery_friction_detected);
CREATE INDEX idx_analyzed_segment ON analyzed_reviews(user_segment_signal);
CREATE INDEX idx_analyzed_sentiment ON analyzed_reviews(sentiment);
```

### Table: clusters

```sql
CREATE TABLE clusters (
    id TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    theme TEXT NOT NULL,
    is_discovery_related BOOLEAN NOT NULL,
    size INTEGER NOT NULL,
    avg_sentiment_score REAL,
    discovery_friction_rate REAL,
    dominant_platform TEXT,
    dominant_emotion TEXT,
    trend_direction TEXT,
    trend_volume_change_pct REAL,
    created_at TIMESTAMP NOT NULL,
    schema_version TEXT NOT NULL DEFAULT '1.0'
);

CREATE TABLE cluster_members (
    cluster_id TEXT NOT NULL REFERENCES clusters(id),
    review_id TEXT NOT NULL REFERENCES analyzed_reviews(id),
    is_representative BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (cluster_id, review_id)
);
```

### Table: insights

```sql
CREATE TABLE insights (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    insight_type TEXT NOT NULL,  -- jtbd | problem | opportunity | unmet_need | segment
    affected_segment TEXT,
    frequency_score REAL,
    severity_score REAL,
    uniqueness_score REAL,
    opportunity_score REAL,
    confidence TEXT NOT NULL,
    confidence_score REAL NOT NULL,
    reasoning TEXT,
    discovery_friction_related BOOLEAN,
    trend_direction TEXT,
    generated_at TIMESTAMP NOT NULL,
    schema_version TEXT NOT NULL DEFAULT '1.0'
);

CREATE TABLE insight_clusters (
    insight_id TEXT NOT NULL REFERENCES insights(id),
    cluster_id TEXT NOT NULL REFERENCES clusters(id),
    PRIMARY KEY (insight_id, cluster_id)
);

CREATE TABLE insight_reviews (
    insight_id TEXT NOT NULL REFERENCES insights(id),
    review_id TEXT NOT NULL REFERENCES analyzed_reviews(id),
    verbatim TEXT,
    PRIMARY KEY (insight_id, review_id)
);
```

### Table: jtbd_profiles

```sql
CREATE TABLE jtbd_profiles (
    id TEXT PRIMARY KEY,
    job_statement TEXT NOT NULL,
    short_label TEXT NOT NULL,
    satisfaction_score REAL,
    gap_description TEXT,
    confidence_score REAL NOT NULL,
    generated_at TIMESTAMP NOT NULL
);
```

### Table: user_segments

```sql
CREATE TABLE user_segments (
    id TEXT PRIMARY KEY,
    segment_label TEXT NOT NULL,
    description TEXT,
    review_count INTEGER,
    fraction_of_total REAL,
    discovery_friction_rate REAL,
    platform_affinity TEXT,
    generated_at TIMESTAMP NOT NULL
);
```

---

## Vector Store Design

### ChromaDB Collections

**Collection: reviews**
- Document: `clean_text`
- Embedding: 384-dim from sentence-transformers
- Metadata: `platform`, `sentiment`, `discovery_friction_detected`, `quality_score`
- Use: Semantic search over review content

**Collection: insights**
- Document: `title + description + reasoning`
- Embedding: 384-dim from sentence-transformers
- Metadata: `insight_type`, `opportunity_score`, `confidence`, `affected_segment`
- Use: Find similar insights, answer PM natural language queries

**Collection: verbatims**
- Document: Direct quote verbatims from supporting_verbatims
- Embedding: 384-dim
- Metadata: `insight_id`, `cluster_id`, `source_review_id`, `platform`
- Use: "Find me reviews where users said X"

---

## Repository Pattern

Each data type has a dedicated repository class with a defined interface:

```python
class ReviewRepository:
    def save(self, review: NormalizedReview) -> None: ...
    def get_by_id(self, id: str) -> NormalizedReview: ...
    def find_by_platform(self, platform: str) -> list[NormalizedReview]: ...
    def find_with_friction(self) -> list[AnalyzedReview]: ...

class InsightRepository:
    def save(self, insight: ProductInsight) -> None: ...
    def get_by_id(self, id: str) -> ProductInsight: ...
    def find_by_type(self, insight_type: str) -> list[ProductInsight]: ...
    def find_top_opportunities(self, limit: int) -> list[ProductInsight]: ...
    def get_evidence(self, insight_id: str) -> list[str]: ...

class ClusterRepository:
    def save(self, cluster: ReviewCluster) -> None: ...
    def get_by_id(self, id: str) -> ReviewCluster: ...
    def find_discovery_related(self) -> list[ReviewCluster]: ...
    def find_by_trend(self, direction: str) -> list[ReviewCluster]: ...
```

---

## Directory Structure

```
phase-6-storage/
├── README.md                       ← This file
├── schemas/
│   ├── __init__.py
│   ├── v1.0/
│   │   ├── raw_reviews.sql
│   │   ├── normalized_reviews.sql
│   │   ├── analyzed_reviews.sql
│   │   ├── clusters.sql
│   │   ├── insights.sql
│   │   └── jtbd_profiles.sql
│   └── schema_registry.py          ← Maps schema versions to DDL files
├── repositories/
│   ├── __init__.py
│   ├── base_repository.py          ← Abstract base with connection management
│   ├── raw_review_repository.py
│   ├── normalized_review_repository.py
│   ├── analyzed_review_repository.py
│   ├── cluster_repository.py
│   ├── insight_repository.py
│   └── jtbd_repository.py
├── vector-store/
│   ├── __init__.py
│   ├── chroma_client.py            ← ChromaDB connection and collection management
│   ├── review_collection.py        ← Reviews vector operations
│   ├── insight_collection.py       ← Insights vector operations
│   └── verbatim_collection.py      ← Verbatim quotes vector operations
├── migrations/
│   ├── 001_initial_schema.sql
│   └── migration_runner.py
├── tests/
│   ├── test_repositories.py
│   ├── test_vector_store.py
│   └── fixtures/
│       └── seed_data.py
├── loader.py                       ← Loads JSONL from all phases into DB
└── database.py                     ← SQLite/PostgreSQL connection factory
```

---

## Data Lineage Map

The evidence index maintained in memory (and optionally persisted as JSON) allows O(1) lookups:

```json
{
  "review_lineage": {
    "raw_review_id": "normalized_id → analyzed_id → [cluster_ids] → [insight_ids]"
  },
  "insight_evidence": {
    "insight_id": {
      "cluster_ids": ["uuid"],
      "review_ids": ["uuid"],
      "verbatims": ["quote text"]
    }
  }
}
```

---

## Configuration

```python
class StorageConfig:
    db_type: str = "sqlite"          # sqlite | postgresql
    db_path: str = "data/knowledge_base.db"
    chroma_persist_dir: str = "data/chroma"
    embedding_model: str = "all-MiniLM-L6-v2"
    schema_version: str = "1.0"
```

---

## Testing Strategy

| Test Type | Coverage |
|---|---|
| Unit | Each repository saves and retrieves correctly |
| Unit | Vector store finds semantically similar documents |
| Unit | Migration runner applies DDL without errors |
| Integration | Full loader populates DB from sample JSONL files |
| Regression | Schema changes detected via schema_version mismatch |

---

## Success Criteria

- All records from Phases 1–5 are stored with schema_version
- Every insight query returns associated verbatims (evidence)
- Vector search returns relevant results for known queries
- Database is idempotent: loading same JSONL twice produces same state
- Migrations can be run without data loss

---

## Dependencies

- `sqlite3` (stdlib) / `psycopg2` — Relational DB
- `chromadb` — Vector store
- `pydantic` — Schema validation before write
- `sentence-transformers` — Embedding generation for vector store

---

## Phase 6 → Phase 7 Contract

Phase 7 reads exclusively from Phase 6 repositories and vector store.
Phase 7 never reads JSONL files directly — only via the repository layer.
