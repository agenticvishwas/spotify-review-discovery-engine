"""Tests for SegmentProfiler."""

import asyncio
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from segments.segment_profiler import SegmentProfiler, _compute_stats, _top_n
from schemas.product_insight import UserSegment


def _make_review(**kwargs) -> dict:
    defaults = {
        "id": str(uuid.uuid4()),
        "normalized_review_id": str(uuid.uuid4()),
        "user_segment_signal": "casual",
        "sentiment": "positive",
        "sentiment_score": 0.5,
        "discovery_friction_detected": False,
        "primary_complaint": None,
        "primary_praise": "Good playlists",
        "feature_mentions": ["Discover Weekly"],
        "platform": "app_store",
        "analysis_status": "success",
        "clean_text": "Great app for discovering music",
    }
    defaults.update(kwargs)
    return defaults


def _make_mock_client(description: str = "Test description") -> MagicMock:
    client = MagicMock()
    client.call = AsyncMock(
        return_value=(
            {
                "description": description,
                "primary_jtbd": "Find new music easily.",
                "primary_pain": "Too many ads.",
                "behavioral_signals": ["listens casually", "uses shuffle", "rarely creates playlists"],
            },
            200,
            "claude-sonnet-4-6",
        )
    )
    return client


# ── Unit: _compute_stats ──────────────────────────────────────────────────────

class TestComputeStats:
    def test_basic_stats(self):
        reviews = [
            _make_review(sentiment_score=0.5, discovery_friction_detected=False, platform="app_store"),
            _make_review(sentiment_score=-0.3, discovery_friction_detected=True, platform="app_store"),
            _make_review(sentiment_score=0.8, discovery_friction_detected=False, platform="reddit"),
        ]
        stats = _compute_stats(reviews, total=10)
        assert stats["count"] == 3
        assert stats["fraction"] == pytest.approx(0.3)
        assert stats["friction_rate"] == pytest.approx(1 / 3)
        assert stats["dominant_platform"] == "app_store"
        assert "avg_sentiment" in stats

    def test_empty_reviews(self):
        stats = _compute_stats([], total=100)
        assert stats["count"] == 0
        assert stats["fraction"] == 0.0
        assert stats["friction_rate"] == 0.0

    def test_top_complaints(self):
        reviews = [
            _make_review(primary_complaint="Too many ads"),
            _make_review(primary_complaint="Too many ads"),
            _make_review(primary_complaint="App crashes"),
        ]
        stats = _compute_stats(reviews, total=10)
        assert stats["top_complaints"][0] == "Too many ads"

    def test_top_features_mentioned(self):
        reviews = [
            _make_review(feature_mentions=["Discover Weekly", "Radio"]),
            _make_review(feature_mentions=["Discover Weekly"]),
        ]
        stats = _compute_stats(reviews, total=10)
        assert "Discover Weekly" in stats["top_feature_mentions"]


# ── Unit: _top_n ──────────────────────────────────────────────────────────────

class TestTopN:
    def test_returns_n_items(self):
        from collections import Counter
        c = Counter({"a": 5, "b": 3, "c": 1})
        assert _top_n(c, 2) == ["a", "b"]

    def test_empty_counter(self):
        from collections import Counter
        assert _top_n(Counter(), 3) == []


# ── Integration: SegmentProfiler with mock LLM ───────────────────────────────

class TestSegmentProfiler:
    def test_profile_all_returns_user_segments(self):
        client = _make_mock_client("Casual users who listen to top hits.")
        profiler = SegmentProfiler(client)

        reviews = [_make_review(user_segment_signal="casual") for _ in range(10)]
        segments = asyncio.run(profiler.profile_all(reviews))

        assert len(segments) == 1
        seg = segments[0]
        assert isinstance(seg, UserSegment)
        assert seg.segment_label == "casual"
        assert seg.review_count == 10

    def test_segments_below_threshold_are_skipped(self):
        client = _make_mock_client()
        profiler = SegmentProfiler(client)

        # Only 2 reviews for power_user — below _MIN_SEGMENT_REVIEWS=5
        reviews = [_make_review(user_segment_signal="power_user") for _ in range(2)]
        segments = asyncio.run(profiler.profile_all(reviews))

        assert len(segments) == 0

    def test_multiple_segments_profiled(self):
        client = _make_mock_client()
        profiler = SegmentProfiler(client)

        reviews = (
            [_make_review(user_segment_signal="casual") for _ in range(8)]
            + [_make_review(user_segment_signal="power_user") for _ in range(6)]
        )
        segments = asyncio.run(profiler.profile_all(reviews))

        labels = {s.segment_label for s in segments}
        assert "casual" in labels
        assert "power_user" in labels

    def test_fraction_of_total_sums_correctly(self):
        client = _make_mock_client()
        profiler = SegmentProfiler(client)

        reviews = (
            [_make_review(user_segment_signal="casual") for _ in range(6)]
            + [_make_review(user_segment_signal="new") for _ in range(6)]
        )
        segments = asyncio.run(profiler.profile_all(reviews, total_reviews=12))

        fracs = [s.fraction_of_total for s in segments]
        assert all(0.0 <= f <= 1.0 for f in fracs)
        assert abs(sum(fracs) - 1.0) < 0.01

    def test_llm_failure_produces_fallback_segment(self):
        from llm.insight_llm_client import InsightLLMError
        client = MagicMock()
        client.call = AsyncMock(side_effect=InsightLLMError("timeout"))
        profiler = SegmentProfiler(client)

        reviews = [_make_review(user_segment_signal="churned") for _ in range(7)]
        segments = asyncio.run(profiler.profile_all(reviews))

        assert len(segments) == 1
        assert "unavailable" in segments[0].description.lower()

    def test_discovery_friction_rate_in_unit_interval(self):
        client = _make_mock_client()
        profiler = SegmentProfiler(client)

        reviews = [
            _make_review(user_segment_signal="casual", discovery_friction_detected=True)
            for _ in range(6)
        ]
        segments = asyncio.run(profiler.profile_all(reviews))
        assert 0.0 <= segments[0].discovery_friction_rate <= 1.0
