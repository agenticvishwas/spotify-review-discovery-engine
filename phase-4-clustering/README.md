# Phase 4 — Clustering & Pattern Recognition

## Objective

Group semantically related reviews into coherent clusters, identify recurring themes, and detect trends over time.

This phase converts thousands of individual data points into a smaller set of meaningful patterns that Insight Generation can reason about at scale.

---

## Responsibilities

- Generate text embeddings for each analyzed review
- Cluster reviews by semantic similarity
- Label each cluster with a human-readable theme
- Detect trend direction for each cluster over time
- Identify dominant signals within clusters (sentiment, friction rate, platform)

---

## Non-Responsibilities

- Analyzing individual reviews (Phase 3)
- Generating product insights or opportunities (Phase 5)
- Storing results permanently (Phase 6)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│         INPUT: AnalyzedReview[] from Phase 3                    │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                   EMBEDDING GENERATION                          │
│                                                                 │
│  EmbeddingEngine                                                │
│  → Model: all-MiniLM-L6-v2 (sentence-transformers)             │
│  → Input: clean_text + jtbd_signal + primary_complaint          │
│  → Output: 384-dimensional float vector per review              │
│  → Cached by review ID (never re-embed same review)             │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                   DIMENSIONALITY REDUCTION                      │
│                                                                 │
│  UMAPReducer                                                    │
│  → Reduce 384-dim → 50-dim for clustering performance           │
│  → n_neighbors: 15, min_dist: 0.1, metric: cosine              │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                   CLUSTERING                                    │
│                                                                 │
│  HDBSCANClusterer                                               │
│  → min_cluster_size: 10 reviews                                 │
│  → min_samples: 5                                               │
│  → metric: euclidean (on UMAP output)                           │
│  → Noise points (-1 label): sent to fallback k-means            │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                   CLUSTER LABELING                              │
│                                                                 │
│  LLM-Assisted Theme Labeler                                     │
│  → Sample 5 representative reviews per cluster                  │
│  → Ask Claude: "What is the common theme?"                      │
│  → Output: label (short), theme (1 sentence), discovery_related?│
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                   TREND ANALYSIS                                │
│                                                                 │
│  TrendAnalyzer                                                  │
│  → Group cluster members by month                               │
│  → Compute volume change: last 90 days vs prior 90 days         │
│  → Label: increasing | stable | decreasing                      │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│         OUTPUT: ReviewCluster[] (JSONL)                         │
│         + clustering_quality_report.json                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Model

### ReviewCluster Schema

```json
{
  "id": "uuid-v4",
  "label": "short human-readable cluster name",
  "theme": "one-sentence description of the common pattern",
  "is_discovery_related": "boolean",
  "member_review_ids": ["uuid — links to AnalyzedReview.id"],
  "representative_review_ids": ["uuid — top 5 most central reviews"],
  "centroid_embedding": "[float] — 384-dim mean embedding",
  "size": "integer",
  "avg_sentiment_score": "float",
  "discovery_friction_rate": "0.0–1.0 — fraction of members with friction=true",
  "dominant_platform": "string",
  "platform_distribution": {"app_store": 0.4, "reddit": 0.3},
  "dominant_emotion": "string",
  "top_features_mentioned": ["string"],
  "trend_direction": "increasing | stable | decreasing",
  "trend_volume_change_pct": "float",
  "created_at": "ISO8601",
  "schema_version": "1.0",
  "clustering_algorithm": "hdbscan",
  "labeling_model": "claude-sonnet-4-6",
  "labeling_prompt_version": "1.0"
}
```

### EmbeddingCache Schema

```json
{
  "review_id": "uuid",
  "embedding": "[float — 384 dimensions]",
  "model": "all-MiniLM-L6-v2",
  "embedded_at": "ISO8601"
}
```

---

## Component Specifications

### EmbeddingEngine

- Model: `sentence-transformers/all-MiniLM-L6-v2`
- Runs locally — no API call, no cost per review
- Input construction: `"{clean_text} {jtbd_signal or ''} {primary_complaint or ''}"`
- Batch size: 64 reviews per GPU/CPU batch
- Cache: `embeddings/cache/{review_id}.npy` — skip if exists

### UMAPReducer

- Purpose: Improve clustering quality by reducing embedding dimensionality
- Parameters: `n_components=50, n_neighbors=15, min_dist=0.1, metric='cosine'`
- Output: 50-dimensional reduced vectors
- Note: UMAP is non-deterministic. Fix `random_state=42` for reproducibility.

### HDBSCANClusterer

- Chosen over k-means because:
  - Does not require specifying number of clusters in advance
  - Handles variable cluster densities
  - Marks outliers explicitly (label = -1) rather than forcing them into clusters
- Parameters: `min_cluster_size=10, min_samples=5`
- Fallback: noise points (label=-1) clustered via k-means with k=5

### ThemeLabeler

- Input: 5 representative reviews per cluster (highest cosine similarity to centroid)
- Prompt: structured, returns `label`, `theme`, `is_discovery_related`
- Confidence guard: if label is generic ("mixed feedback"), flag for human review
- Batched: all clusters labeled in a single LLM call with multi-cluster prompt

**Cluster Labeling Prompt v1.0:**
```
You are a product research analyst. Below are 5 user reviews that belong to the same cluster.
Identify the common theme across these reviews.

Reviews:
{review_1}
{review_2}
{review_3}
{review_4}
{review_5}

Return JSON with:
{
  "label": "short 3-5 word label for this cluster",
  "theme": "one sentence describing the common pattern",
  "is_discovery_related": true/false,
  "confidence": 0.0-1.0
}
```

### TrendAnalyzer

- Divides reviews into 30-day windows by `published_at`
- Computes cluster volume per window
- Compares last 90 days vs prior 90 days
- Classification rules:
  - `increasing`: volume change > +20%
  - `decreasing`: volume change < -20%
  - `stable`: between -20% and +20%

---

## Directory Structure

```
phase-4-clustering/
├── README.md                       ← This file
├── embeddings/
│   ├── __init__.py
│   ├── embedding_engine.py         ← sentence-transformers wrapper
│   ├── embedding_cache.py          ← Read/write .npy cache files
│   └── umap_reducer.py             ← UMAP dimensionality reduction
├── clustering/
│   ├── __init__.py
│   ├── hdbscan_clusterer.py        ← Primary clustering algorithm
│   ├── fallback_clusterer.py       ← k-means fallback for noise points
│   └── cluster_assembler.py        ← Builds ReviewCluster objects
├── themes/
│   ├── __init__.py
│   ├── theme_labeler.py            ← LLM-based cluster theme generation
│   ├── prompts/
│   │   └── cluster_labeling_v1.0.md
│   └── trend_analyzer.py           ← Volume trend detection
├── tests/
│   ├── test_embedding_engine.py
│   ├── test_hdbscan_clusterer.py
│   ├── test_theme_labeler.py
│   └── test_trend_analyzer.py
├── clustering_pipeline.py          ← Orchestrates full clustering run
└── quality_report.py               ← Cluster quality metrics
```

---

## Pipeline Flow

```
1. Load AnalyzedReview JSONL from Phase 3
2. EmbeddingEngine:
   a. Check cache for each review_id
   b. Generate embeddings for uncached reviews
   c. Save to cache
3. UMAPReducer → reduce 384-dim to 50-dim
4. HDBSCANClusterer → assign cluster labels
5. FallbackClusterer → handle noise points (-1 labels)
6. ClusterAssembler → build ReviewCluster objects:
   a. Compute centroid embedding (mean of member embeddings)
   b. Find representative reviews (nearest to centroid)
   c. Compute aggregate metrics (friction rate, sentiment, platform dist)
7. ThemeLabeler → LLM call to label each cluster
8. TrendAnalyzer → compute trend direction per cluster
9. Write ReviewCluster JSONL
10. Emit clustering_quality_report.json
```

---

## Quality Report Output

```json
{
  "run_date": "ISO8601",
  "total_reviews_input": 1847,
  "total_clusters": 34,
  "noise_points": 89,
  "noise_rate": 0.048,
  "avg_cluster_size": 51,
  "largest_cluster_size": 312,
  "discovery_related_clusters": 18,
  "discovery_cluster_rate": 0.53,
  "labeling_confidence": {
    "avg": 0.81,
    "below_threshold": 4
  },
  "trend_distribution": {
    "increasing": 8,
    "stable": 22,
    "decreasing": 4
  }
}
```

---

## Testing Strategy

| Test Type | Coverage |
|---|---|
| Unit | EmbeddingEngine produces consistent vectors for same input |
| Unit | HDBSCAN correctly clusters synthetic test data |
| Unit | TrendAnalyzer correctly classifies known trend patterns |
| Unit | ThemeLabeler validates response schema |
| Integration | Full pipeline produces non-empty clusters from sample reviews |
| Regression | Cluster count stays within expected range for known dataset |

---

## Success Criteria

- Every AnalyzedReview is assigned to a cluster (including noise cluster)
- Noise rate < 10% of total reviews
- All clusters have human-readable labels
- Discovery-related clusters are correctly flagged
- Trend direction is computed for all clusters
- Embedding cache prevents re-embedding on subsequent runs

---

## Dependencies

- `sentence-transformers` — Local embedding model
- `umap-learn` — Dimensionality reduction
- `hdbscan` — Primary clustering
- `scikit-learn` — Fallback k-means
- `numpy` — Embedding math
- `anthropic` — Cluster theme labeling

---

## Phase 4 → Phase 5 Contract

Phase 4 writes JSONL files conforming to ReviewCluster schema.
Phase 5 reads those clusters to generate Jobs To Be Done, user segments, and opportunity scores.
