PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA cache_size = -64000;

-- ---------------------------------------------------------------------------
-- Pipeline run tracking
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id                      TEXT PRIMARY KEY,
    started_at              TEXT NOT NULL,
    completed_at            TEXT,
    status                  TEXT NOT NULL DEFAULT 'running',
    phase1_loaded           INTEGER NOT NULL DEFAULT 0,
    phase2_loaded           INTEGER NOT NULL DEFAULT 0,
    phase3_loaded           INTEGER NOT NULL DEFAULT 0,
    phase4_loaded           INTEGER NOT NULL DEFAULT 0,
    phase5_loaded           INTEGER NOT NULL DEFAULT 0,
    raw_review_count        INTEGER NOT NULL DEFAULT 0,
    normalized_review_count INTEGER NOT NULL DEFAULT 0,
    analyzed_review_count   INTEGER NOT NULL DEFAULT 0,
    cluster_count           INTEGER NOT NULL DEFAULT 0,
    insight_count           INTEGER NOT NULL DEFAULT 0,
    error_log               TEXT,
    schema_version          TEXT NOT NULL DEFAULT '1.0'
);

-- ---------------------------------------------------------------------------
-- Phase 1 — Raw Reviews
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS raw_reviews (
    id                  TEXT PRIMARY KEY,
    source_platform     TEXT NOT NULL,
    raw_text            TEXT NOT NULL,
    rating              INTEGER,
    author_id           TEXT,
    published_at        TEXT NOT NULL,
    source_url          TEXT NOT NULL DEFAULT '',
    ingested_at         TEXT NOT NULL,
    ingestion_batch_id  TEXT NOT NULL,
    schema_version      TEXT NOT NULL DEFAULT '1.0',
    loaded_at           TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_raw_platform  ON raw_reviews(source_platform);
CREATE INDEX IF NOT EXISTS idx_raw_batch     ON raw_reviews(ingestion_batch_id);
CREATE INDEX IF NOT EXISTS idx_raw_published ON raw_reviews(published_at);

-- ---------------------------------------------------------------------------
-- Phase 2 — Normalized Reviews
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS normalized_reviews (
    id                  TEXT PRIMARY KEY,
    source_review_id    TEXT NOT NULL,
    clean_text          TEXT NOT NULL,
    normalized_rating   REAL,
    language            TEXT NOT NULL DEFAULT 'unknown',
    word_count          INTEGER NOT NULL DEFAULT 0,
    sentence_count      INTEGER,
    quality_score       REAL NOT NULL DEFAULT 0.0,
    is_duplicate        INTEGER NOT NULL DEFAULT 0,
    duplicate_of_id     TEXT,
    platform            TEXT NOT NULL,
    published_at        TEXT,
    normalized_at       TEXT NOT NULL,
    filters_applied     TEXT,
    schema_version      TEXT NOT NULL DEFAULT '1.0',
    loaded_at           TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (source_review_id) REFERENCES raw_reviews(id)
);

CREATE INDEX IF NOT EXISTS idx_norm_source    ON normalized_reviews(source_review_id);
CREATE INDEX IF NOT EXISTS idx_norm_platform  ON normalized_reviews(platform);
CREATE INDEX IF NOT EXISTS idx_norm_language  ON normalized_reviews(language);
CREATE INDEX IF NOT EXISTS idx_norm_quality   ON normalized_reviews(quality_score);
CREATE INDEX IF NOT EXISTS idx_norm_duplicate ON normalized_reviews(is_duplicate);

-- ---------------------------------------------------------------------------
-- Phase 3 — Analyzed Reviews
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS analyzed_reviews (
    id                              TEXT PRIMARY KEY,
    normalized_review_id            TEXT NOT NULL,
    source_review_id                TEXT NOT NULL DEFAULT '',
    sentiment                       TEXT NOT NULL,
    sentiment_score                 REAL NOT NULL DEFAULT 0.0,
    discovery_friction_detected     INTEGER NOT NULL DEFAULT 0,
    discovery_friction_description  TEXT,
    primary_complaint               TEXT,
    primary_praise                  TEXT,
    feature_mentions                TEXT,
    jtbd_signal                     TEXT,
    user_intent                     TEXT,
    root_cause_signal               TEXT,
    user_segment_signal             TEXT NOT NULL DEFAULT 'unknown',
    emotion_tags                    TEXT,
    listening_behavior_signal       TEXT,
    confidence_score                REAL NOT NULL DEFAULT 0.0,
    analysis_model                  TEXT NOT NULL DEFAULT '',
    prompt_version                  TEXT NOT NULL DEFAULT '',
    analyzed_at                     TEXT NOT NULL,
    analysis_tokens_used            INTEGER NOT NULL DEFAULT 0,
    analysis_status                 TEXT NOT NULL DEFAULT 'success',
    schema_version                  TEXT NOT NULL DEFAULT '1.0',
    loaded_at                       TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (normalized_review_id) REFERENCES normalized_reviews(id)
);

CREATE INDEX IF NOT EXISTS idx_analyzed_norm       ON analyzed_reviews(normalized_review_id);
CREATE INDEX IF NOT EXISTS idx_analyzed_sentiment  ON analyzed_reviews(sentiment);
CREATE INDEX IF NOT EXISTS idx_analyzed_friction   ON analyzed_reviews(discovery_friction_detected);
CREATE INDEX IF NOT EXISTS idx_analyzed_segment    ON analyzed_reviews(user_segment_signal);
CREATE INDEX IF NOT EXISTS idx_analyzed_confidence ON analyzed_reviews(confidence_score);
CREATE INDEX IF NOT EXISTS idx_analyzed_status     ON analyzed_reviews(analysis_status);

-- ---------------------------------------------------------------------------
-- Phase 4 — Clusters
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS clusters (
    id                       TEXT PRIMARY KEY,
    label                    TEXT NOT NULL,
    theme                    TEXT NOT NULL,
    is_discovery_related     INTEGER NOT NULL DEFAULT 0,
    size                     INTEGER NOT NULL DEFAULT 0,
    avg_sentiment_score      REAL,
    discovery_friction_rate  REAL,
    dominant_platform        TEXT,
    platform_distribution    TEXT,
    dominant_emotion         TEXT,
    top_features_mentioned   TEXT,
    trend_direction          TEXT,
    trend_volume_change_pct  REAL,
    is_micro_cluster         INTEGER NOT NULL DEFAULT 0,
    labeling_confidence      REAL,
    review_required          INTEGER NOT NULL DEFAULT 0,
    clustering_algorithm     TEXT NOT NULL DEFAULT 'hdbscan',
    labeling_model           TEXT,
    labeling_prompt_version  TEXT,
    created_at               TEXT NOT NULL,
    schema_version           TEXT NOT NULL DEFAULT '1.0',
    loaded_at                TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_cluster_friction  ON clusters(discovery_friction_rate);
CREATE INDEX IF NOT EXISTS idx_cluster_trend     ON clusters(trend_direction);
CREATE INDEX IF NOT EXISTS idx_cluster_micro     ON clusters(is_micro_cluster);
CREATE INDEX IF NOT EXISTS idx_cluster_sentiment ON clusters(avg_sentiment_score);
CREATE INDEX IF NOT EXISTS idx_cluster_size      ON clusters(size);

-- Cluster membership (M:N resolved to rows)
CREATE TABLE IF NOT EXISTS cluster_members (
    cluster_id        TEXT NOT NULL,
    review_id         TEXT NOT NULL,
    is_representative INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (cluster_id, review_id),
    FOREIGN KEY (cluster_id) REFERENCES clusters(id)
);

CREATE INDEX IF NOT EXISTS idx_cm_review ON cluster_members(review_id);

-- ---------------------------------------------------------------------------
-- Phase 5 — Product Insights
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS insights (
    id                          TEXT PRIMARY KEY,
    title                       TEXT NOT NULL,
    description                 TEXT NOT NULL,
    insight_type                TEXT NOT NULL,
    affected_segment            TEXT,
    frequency_score             REAL,
    severity_score              REAL,
    uniqueness_score            REAL,
    opportunity_score           REAL,
    confidence                  TEXT NOT NULL,
    confidence_score            REAL NOT NULL DEFAULT 0.0,
    reasoning                   TEXT,
    discovery_friction_related  INTEGER NOT NULL DEFAULT 0,
    trend_direction             TEXT,
    review_required             INTEGER NOT NULL DEFAULT 0,
    supporting_verbatims        TEXT,
    generation_model            TEXT,
    prompt_version              TEXT,
    generated_at                TEXT NOT NULL,
    schema_version              TEXT NOT NULL DEFAULT '1.0',
    loaded_at                   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_insight_type        ON insights(insight_type);
CREATE INDEX IF NOT EXISTS idx_insight_confidence  ON insights(confidence_score);
CREATE INDEX IF NOT EXISTS idx_insight_opportunity ON insights(opportunity_score);
CREATE INDEX IF NOT EXISTS idx_insight_pending     ON insights(review_required);
CREATE INDEX IF NOT EXISTS idx_insight_friction    ON insights(discovery_friction_related);

CREATE TABLE IF NOT EXISTS insight_clusters (
    insight_id TEXT NOT NULL,
    cluster_id TEXT NOT NULL,
    PRIMARY KEY (insight_id, cluster_id),
    FOREIGN KEY (insight_id) REFERENCES insights(id),
    FOREIGN KEY (cluster_id) REFERENCES clusters(id)
);

CREATE TABLE IF NOT EXISTS insight_reviews (
    insight_id TEXT NOT NULL,
    review_id  TEXT NOT NULL,
    verbatim   TEXT,
    PRIMARY KEY (insight_id, review_id),
    FOREIGN KEY (insight_id) REFERENCES insights(id)
);

CREATE INDEX IF NOT EXISTS idx_ir_review ON insight_reviews(review_id);

-- Phase 5 JTBD Profiles
CREATE TABLE IF NOT EXISTS jtbd_profiles (
    id                    TEXT PRIMARY KEY,
    job_statement         TEXT NOT NULL,
    short_label           TEXT NOT NULL,
    supporting_cluster_ids TEXT,
    user_segments         TEXT,
    frequency_estimate    INTEGER,
    satisfaction_score    REAL,
    gap_score             REAL,
    confidence_score      REAL,
    gap_description       TEXT,
    generated_at          TEXT NOT NULL,
    generation_model      TEXT,
    prompt_version        TEXT,
    schema_version        TEXT NOT NULL DEFAULT '1.0',
    loaded_at             TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Phase 5 User Segments
CREATE TABLE IF NOT EXISTS user_segments (
    id                      TEXT PRIMARY KEY,
    segment_label           TEXT NOT NULL,
    description             TEXT,
    behavioral_signals      TEXT,
    primary_jtbd            TEXT,
    primary_pain            TEXT,
    review_count            INTEGER,
    fraction_of_total       REAL,
    discovery_friction_rate REAL,
    platform_affinity       TEXT,
    avg_sentiment_score     REAL,
    top_features_mentioned  TEXT,
    generated_at            TEXT NOT NULL,
    generation_model        TEXT,
    schema_version          TEXT NOT NULL DEFAULT '1.0',
    loaded_at               TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Phase 5 Unmet Needs
CREATE TABLE IF NOT EXISTS unmet_needs (
    id                          TEXT PRIMARY KEY,
    need_statement              TEXT NOT NULL,
    supporting_cluster_ids      TEXT,
    affected_segment            TEXT,
    expressed_frequency         INTEGER,
    related_features            TEXT,
    gap_description             TEXT,
    confidence_score            REAL,
    linguistic_patterns_matched TEXT,
    generated_at                TEXT NOT NULL,
    generation_model            TEXT,
    prompt_version              TEXT,
    schema_version              TEXT NOT NULL DEFAULT '1.0',
    loaded_at                   TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------------------
-- Evidence lineage cache (denormalized for fast Phase 7 lookups)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS lineage (
    raw_review_id        TEXT PRIMARY KEY,
    normalized_review_id TEXT,
    analyzed_review_id   TEXT,
    cluster_ids          TEXT,
    insight_ids          TEXT
);

CREATE INDEX IF NOT EXISTS idx_lineage_norm     ON lineage(normalized_review_id);
CREATE INDEX IF NOT EXISTS idx_lineage_analyzed ON lineage(analyzed_review_id);
