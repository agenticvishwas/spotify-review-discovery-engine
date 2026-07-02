"""Tests for Phase 6 loaders — use temp JSONL fixtures, no real data required."""
from __future__ import annotations
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from loaders.raw_review_loader import RawReviewLoader
from loaders.normalized_loader import NormalizedLoader
from loaders.analyzed_loader import AnalyzedLoader
from loaders.cluster_loader import ClusterLoader
from loaders.insight_loader import InsightLoader


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


@pytest.fixture
def raw_dir(tmp_path):
    data = [
        {"id": "r1", "source_platform": "app_store", "raw_text": "Great app",
         "rating": 5, "published_at": "2026-01-01", "source_url": "http://x",
         "ingested_at": "2026-01-01", "ingestion_batch_id": "b1"},
        {"id": "r2", "source_platform": "google_play", "raw_text": "Bad crashes",
         "rating": 1, "published_at": "2026-01-02", "source_url": "http://y",
         "ingested_at": "2026-01-02", "ingestion_batch_id": "b1"},
    ]
    write_jsonl(tmp_path / "2026-01-01" / "b1.jsonl", data)
    return str(tmp_path)


def test_raw_loader_happy(raw_dir):
    loader = RawReviewLoader(raw_dir)
    records, skipped = loader.load_all()
    assert len(records) == 2
    assert skipped == 0
    assert records[0]["id"] == "r1"
    assert records[1]["source_platform"] == "google_play"


def test_raw_loader_skips_missing_id(tmp_path):
    write_jsonl(tmp_path / "2026-01-01" / "b.jsonl", [{"source_platform": "app_store", "raw_text": "x"}])
    loader = RawReviewLoader(str(tmp_path))
    records, skipped = loader.load_all()
    assert len(records) == 0
    assert skipped == 1


def test_raw_loader_missing_dir():
    loader = RawReviewLoader("/nonexistent/path")
    records, skipped = loader.load_all()
    assert records == []
    assert skipped == 0


def test_normalized_loader(tmp_path):
    data = [{"id": "n1", "source_review_id": "r1", "clean_text": "Great app",
             "language": "en", "word_count": 2, "quality_score": 0.8,
             "is_duplicate": False, "platform": "app_store", "normalized_at": "2026-01-01"}]
    write_jsonl(tmp_path / "2026-01-01" / "b.jsonl", data)
    loader = NormalizedLoader(str(tmp_path))
    records, skipped = loader.load_all()
    assert len(records) == 1
    assert records[0]["is_duplicate"] == 0  # coerced to int
    assert records[0]["filters_applied"] == "[]"  # default empty list serialized


def test_cluster_loader(tmp_path):
    data = [{
        "id": "c1", "label": "Audio bugs", "theme": "Audio quality issues",
        "size": 10, "member_review_ids": ["r1", "r2", "r3"],
        "representative_review_ids": ["r1"], "created_at": "2026-01-01",
        "discovery_friction_rate": 0.4,
    }]
    write_jsonl(tmp_path / "2026-01-01" / "b.jsonl", data)
    loader = ClusterLoader(str(tmp_path))
    clusters, members, skipped = loader.load_all()  # type: ignore[misc]
    assert len(clusters) == 1
    assert len(members) == 3
    reps = [m for m in members if m["is_representative"] == 1]
    assert len(reps) == 1
    assert reps[0]["review_id"] == "r1"


def test_insight_loader(tmp_path):
    insights = [{
        "id": "i1", "title": "Users want offline mode", "description": "Many want downloads",
        "insight_type": "unmet_need", "confidence": "high", "confidence_score": 0.85,
        "supporting_cluster_ids": ["c1"], "supporting_review_ids": ["r1"],
        "supporting_verbatims": ["I need offline"], "generated_at": "2026-01-01",
    }]
    write_jsonl(tmp_path / "2026-01-01" / "product_insights_b1.jsonl", insights)
    loader = InsightLoader(str(tmp_path))
    ins, ic, ir, skipped = loader.load_insights()
    assert len(ins) == 1
    assert len(ic) == 1
    assert len(ir) == 1
    assert ins[0]["confidence_score"] == 0.85
