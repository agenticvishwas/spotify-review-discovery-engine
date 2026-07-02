"""Tests for BatchProcessor using a mock LLMClient — no real API calls."""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "phase-2-preprocessing"))

import pytest
from models.normalized_review import NormalizedReview
from analyzers.batch_processor import BatchProcessor
from analyzers.llm_client import LLMExtractionError
from schemas.analyzed_review import AnalyzedReview


def _make_review(idx: int = 0, **overrides) -> NormalizedReview:
    defaults = dict(
        id=f"norm-{idx:03d}",
        source_review_id=f"raw-{idx:03d}",
        clean_text="Discover Weekly stopped working for me. Very frustrated.",
        normalized_rating=2.0,
        language="en",
        word_count=8,
        sentence_count=1,
        quality_score=0.8,
        is_duplicate=False,
        platform="google_play",
        published_at="2026-06-01T10:00:00+00:00",
        normalized_at="2026-06-01T10:01:00+00:00",
    )
    defaults.update(overrides)
    return NormalizedReview(**defaults)


VALID_LLM_RESPONSE = {
    "sentiment": "negative",
    "sentiment_score": -0.8,
    "discovery_friction_detected": True,
    "feature_mentions": ["Discover Weekly"],
    "emotion_tags": ["frustration"],
    "user_segment_signal": "casual",
    "listening_behavior_signal": "unknown",
    "confidence_score": 0.82,
}


def _make_mock_client(response: dict = None, error: Exception = None):
    client = MagicMock()
    client.model = "test-model"
    client.prompt_version = "1.3"
    if error:
        client.extract = AsyncMock(side_effect=error)
    else:
        client.extract = AsyncMock(return_value=(response or VALID_LLM_RESPONSE, 300))
    return client


class TestBatchProcessor:
    def test_processes_eligible_reviews(self):
        reviews = [_make_review(i) for i in range(3)]
        client = _make_mock_client()
        processor = BatchProcessor(llm_client=client, concurrency=2)

        results: list[AnalyzedReview] = []
        stats = asyncio.run(
            processor.process(reviews, on_result=results.append)
        )

        assert len(results) == 3
        assert stats.success == 3
        assert stats.failed == 0
        assert stats.skipped == 0

    def test_skips_duplicate_reviews(self):
        reviews = [
            _make_review(0),
            _make_review(1, is_duplicate=True, duplicate_of_id="norm-000"),
        ]
        client = _make_mock_client()
        processor = BatchProcessor(llm_client=client, concurrency=2)

        results: list[AnalyzedReview] = []
        stats = asyncio.run(
            processor.process(reviews, on_result=results.append)
        )

        assert len(results) == 1
        assert stats.skipped == 1

    def test_skips_low_quality_reviews(self):
        reviews = [_make_review(0, quality_score=0.1)]
        client = _make_mock_client()
        processor = BatchProcessor(llm_client=client, concurrency=2)

        results: list[AnalyzedReview] = []
        stats = asyncio.run(
            processor.process(reviews, on_result=results.append)
        )

        assert len(results) == 0
        assert stats.skipped == 1

    def test_skips_already_analyzed_ids(self):
        reviews = [_make_review(0), _make_review(1)]
        client = _make_mock_client()
        processor = BatchProcessor(llm_client=client, concurrency=2)

        results: list[AnalyzedReview] = []
        stats = asyncio.run(
            processor.process(
                reviews,
                on_result=results.append,
                already_analyzed_ids={"norm-000"},
            )
        )

        assert len(results) == 1
        assert stats.skipped == 1

    def test_failed_analysis_produces_failed_record(self):
        reviews = [_make_review(0)]
        client = _make_mock_client(error=LLMExtractionError("no tool_use block"))
        processor = BatchProcessor(llm_client=client, concurrency=1)

        results: list[AnalyzedReview] = []
        stats = asyncio.run(
            processor.process(reviews, on_result=results.append)
        )

        assert len(results) == 1
        assert results[0].analysis_status == "failed"
        assert results[0].confidence_score == 0.0
        assert stats.failed == 1

    def test_low_confidence_result_flagged(self):
        low_conf_response = {**VALID_LLM_RESPONSE, "confidence_score": 0.3}
        reviews = [_make_review(0)]
        client = _make_mock_client(response=low_conf_response)
        processor = BatchProcessor(llm_client=client, concurrency=1)

        results: list[AnalyzedReview] = []
        stats = asyncio.run(
            processor.process(reviews, on_result=results.append)
        )

        assert len(results) == 1
        assert results[0].analysis_status == "low_confidence"
        assert stats.low_confidence == 1

    def test_analyzed_review_has_lineage_fields(self):
        reviews = [_make_review(0)]
        client = _make_mock_client()
        processor = BatchProcessor(llm_client=client, concurrency=1)

        results: list[AnalyzedReview] = []
        asyncio.run(processor.process(reviews, on_result=results.append))

        r = results[0]
        assert r.normalized_review_id == "norm-000"
        assert r.source_review_id == "raw-000"
        assert r.analysis_model == "test-model"
        assert r.prompt_version == "1.3"
        assert r.schema_version == "1.0"
