"""
Tests for ChromaManager.
Skipped automatically when chromadb or sentence-transformers are not installed.
"""
from __future__ import annotations
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

chromadb = pytest.importorskip("chromadb", reason="chromadb not installed")
pytest.importorskip("sentence_transformers", reason="sentence-transformers not installed")

from vector_store.chroma_manager import ChromaManager


@pytest.fixture
def chroma(tmp_path):
    mgr = ChromaManager(
        persist_dir=str(tmp_path / "chroma"),
        embedding_model="all-MiniLM-L6-v2",
        batch_size=10,
    )
    mgr.connect()
    return mgr


def test_upsert_and_search_reviews(chroma):
    rows = [
        {"id": "r1", "clean_text": "Spotify keeps crashing when I shuffle",
         "platform": "app_store", "sentiment": "negative", "sentiment_score": -0.8,
         "discovery_friction_detected": 1, "user_segment_signal": "casual",
         "quality_score": 0.9, "language": "en"},
        {"id": "r2", "clean_text": "Love the discover weekly feature",
         "platform": "google_play", "sentiment": "positive", "sentiment_score": 0.9,
         "discovery_friction_detected": 0, "user_segment_signal": "power_user",
         "quality_score": 0.85, "language": "en"},
    ]
    n = chroma.upsert_reviews(rows)
    assert n == 2

    results = chroma.search_reviews("app keeps crashing", n_results=2)
    assert len(results) >= 1
    assert results[0]["id"] in {"r1", "r2"}


def test_upsert_and_search_insights(chroma):
    rows = [
        {"id": "i1", "title": "Offline download missing", "description": "Users want offline",
         "insight_type": "unmet_need", "confidence_score": 0.85,
         "opportunity_score": 0.9, "discovery_friction_related": 1,
         "affected_segment": "power_user", "review_required": 0},
    ]
    n = chroma.upsert_insights(rows)
    assert n == 1

    results = chroma.search_insights("offline playback")
    assert len(results) == 1
    assert results[0]["id"] == "i1"


def test_upsert_verbatims(chroma):
    n = chroma.upsert_verbatims("i1", ["I need offline mode", "Download feature please"])
    assert n == 2
    results = chroma.search_verbatims("offline music")
    assert len(results) >= 1


def test_collection_counts(chroma):
    chroma.upsert_reviews([
        {"id": "r1", "clean_text": "test review", "platform": "app_store",
         "sentiment": "positive", "sentiment_score": 0.5,
         "discovery_friction_detected": 0, "user_segment_signal": "unknown",
         "quality_score": 0.7, "language": "en"},
    ])
    counts = chroma.collection_counts()
    assert "reviews" in counts
    assert counts["reviews"] >= 1
