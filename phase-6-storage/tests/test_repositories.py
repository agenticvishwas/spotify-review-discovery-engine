"""Tests for SQLite repositories — in-memory DB, no file I/O."""
from __future__ import annotations
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from db.connection import _apply_schema
from repositories.review_repository import ReviewRepository
from repositories.cluster_repository import ClusterRepository
from repositories.insight_repository import InsightRepository
from evidence.lineage_builder import LineageBuilder


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    _apply_schema(c)
    yield c
    c.close()


# ------------------------------------------------------------------
# ReviewRepository
# ------------------------------------------------------------------

def test_upsert_raw(conn):
    repo = ReviewRepository(conn)
    rows = [{"id": "r1", "source_platform": "app_store", "raw_text": "Great",
             "rating": 5, "author_id": None, "published_at": "2026-01-01",
             "source_url": "", "ingested_at": "2026-01-01",
             "ingestion_batch_id": "b1", "schema_version": "1.0"}]
    n = repo.upsert_raw(rows)
    assert n == 1
    rec = repo.get_raw_by_id("r1")
    assert rec is not None
    assert rec["source_platform"] == "app_store"


def test_upsert_raw_idempotent(conn):
    repo = ReviewRepository(conn)
    row = {"id": "r1", "source_platform": "app_store", "raw_text": "Great",
           "rating": 5, "author_id": None, "published_at": "2026-01-01",
           "source_url": "", "ingested_at": "2026-01-01",
           "ingestion_batch_id": "b1", "schema_version": "1.0"}
    repo.upsert_raw([row])
    repo.upsert_raw([row])  # second upsert should not raise
    # Only one row exists
    count = conn.execute("SELECT COUNT(*) FROM raw_reviews").fetchone()[0]
    assert count == 1


def test_count_by_platform(conn):
    repo = ReviewRepository(conn)
    rows = [
        {"id": "r1", "source_platform": "app_store", "raw_text": "A", "rating": None,
         "author_id": None, "published_at": "2026-01-01", "source_url": "",
         "ingested_at": "2026-01-01", "ingestion_batch_id": "b1", "schema_version": "1.0"},
        {"id": "n1", "source_review_id": "r1", "clean_text": "A", "normalized_rating": None,
         "language": "en", "word_count": 1, "sentence_count": 1, "quality_score": 0.8,
         "is_duplicate": 0, "duplicate_of_id": None, "platform": "app_store",
         "published_at": "2026-01-01", "normalized_at": "2026-01-01",
         "filters_applied": "[]", "schema_version": "1.0"},
    ]
    repo.upsert_raw(rows[:1])
    repo.upsert_normalized(rows[1:])
    counts = repo.count_by_platform()
    assert counts["app_store"] == 1


# ------------------------------------------------------------------
# ClusterRepository
# ------------------------------------------------------------------

def test_upsert_cluster(conn):
    repo = ClusterRepository(conn)
    clusters = [{"id": "c1", "label": "Audio", "theme": "Audio bugs",
                 "is_discovery_related": 0, "size": 5, "avg_sentiment_score": -0.3,
                 "discovery_friction_rate": 0.6, "dominant_platform": "app_store",
                 "platform_distribution": "{}", "dominant_emotion": "frustration",
                 "top_features_mentioned": "[]", "trend_direction": "increasing",
                 "trend_volume_change_pct": 10.0, "is_micro_cluster": 0,
                 "labeling_confidence": 0.9, "review_required": 0,
                 "clustering_algorithm": "hdbscan", "labeling_model": "claude",
                 "labeling_prompt_version": "1.0", "created_at": "2026-01-01",
                 "schema_version": "1.0"}]
    n = repo.upsert_clusters(clusters)
    assert n == 1

    members = [
        {"cluster_id": "c1", "review_id": "r1", "is_representative": 1},
        {"cluster_id": "c1", "review_id": "r2", "is_representative": 0},
    ]
    repo.upsert_members(members)
    assert repo.get_members("c1") == ["r1", "r2"]
    assert repo.get_members("c1", representatives_only=True) == ["r1"]


# ------------------------------------------------------------------
# InsightRepository
# ------------------------------------------------------------------

def test_upsert_insight(conn):
    repo = InsightRepository(conn)
    rows = [{"id": "i1", "title": "Offline mode needed", "description": "Many want it",
             "insight_type": "unmet_need", "affected_segment": "power_user",
             "frequency_score": 0.7, "severity_score": 0.8, "uniqueness_score": 0.5,
             "opportunity_score": 0.75, "confidence": "high", "confidence_score": 0.85,
             "reasoning": "Strong signals", "discovery_friction_related": 1,
             "trend_direction": "increasing", "review_required": 0,
             "supporting_verbatims": '["I want offline"]', "generation_model": "claude",
             "prompt_version": "1.0", "generated_at": "2026-01-01",
             "schema_version": "1.0"}]
    n = repo.upsert_insights(rows)
    assert n == 1
    top = repo.top_opportunities(limit=5)
    assert len(top) == 1
    assert top[0]["opportunity_score"] == 0.75

    summary = repo.insight_summary()
    assert summary["total"] == 1
    assert summary["ready"] == 1
    assert summary["pending"] == 0


# ------------------------------------------------------------------
# LineageBuilder
# ------------------------------------------------------------------

def _seed_lineage_data(conn):
    conn.execute("""INSERT INTO raw_reviews VALUES
        ('r1','app_store','text',5,NULL,'2026-01-01','','2026-01-01','b1','1.0',datetime('now'))""")
    conn.execute("""INSERT INTO normalized_reviews VALUES
        ('n1','r1','clean',4.0,'en',5,1,0.8,0,NULL,'app_store','2026-01-01','2026-01-01','[]','1.0',datetime('now'))""")
    conn.execute("""INSERT INTO analyzed_reviews VALUES
        ('a1','n1','r1','positive',0.9,0,NULL,NULL,NULL,'[]',NULL,NULL,NULL,'casual','[]',NULL,0.9,'claude','1.0','2026-01-01',0,'success','1.0',datetime('now'))""")
    conn.execute("INSERT INTO clusters VALUES ('c1','Audio','Audio bugs',0,5,-0.3,0.4,'app_store','{}','frustration','[]','stable',0,0,0.9,0,'hdbscan','claude','1.0','2026-01-01','1.0',datetime('now'))")
    conn.execute("INSERT INTO cluster_members VALUES ('c1','n1',1)")
    conn.execute("""INSERT INTO insights VALUES
        ('i1','Title','Desc','problem','casual',0.5,0.7,0.4,0.6,'high',0.85,'Reasoning',0,'stable',0,'[]','claude','1.0','2026-01-01','1.0',datetime('now'))""")
    conn.execute("INSERT INTO insight_reviews VALUES ('i1','n1',NULL)")
    conn.commit()


def test_lineage_builder(conn):
    _seed_lineage_data(conn)
    lb = LineageBuilder(conn)
    n = lb.build()
    assert n == 1

    lineage = lb.get_lineage("r1")
    assert lineage["normalized_review_id"] == "n1"
    assert lineage["analyzed_review_id"] == "a1"
    assert "c1" in lineage["cluster_ids"]
    assert "i1" in lineage["insight_ids"]
