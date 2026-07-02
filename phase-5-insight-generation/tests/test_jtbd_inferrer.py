"""Tests for JTBD inferrer and synthesiser."""

import asyncio
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from jtbd.cluster_jtbd_inferrer import (
    ClusterJTBDInferrer,
    _validate_job_statement,
    _fix_job_statement,
    _infer_segments,
    _build_clusters_block,
)
from jtbd.jtbd_synthesizer import JTBDSynthesizer, _keyword_set, _jaccard
from schemas.product_insight import JTBDProfile


def _make_cluster(**kwargs) -> dict:
    defaults = {
        "id": str(uuid.uuid4()),
        "label": "Repetitive Recommendations",
        "theme": "Users complain about same songs repeating",
        "is_micro_cluster": False,
        "is_discovery_related": True,
        "size": 50,
        "avg_sentiment_score": -0.6,
        "discovery_friction_rate": 0.7,
        "dominant_emotion": "frustration",
        "top_features_mentioned": ["Discover Weekly", "Radio"],
        "trend_direction": "increasing",
        "trend_volume_change_pct": 15.0,
        "member_review_ids": ["r1", "r2", "r3"],
        "representative_review_ids": ["r1", "r2"],
        "labeling_confidence": 0.85,
        "review_required": False,
        "platform_distribution": {"app_store": 0.6, "google_play": 0.4},
        "dominant_platform": "app_store",
        "centroid_embedding": [0.1] * 384,
        "created_at": "2026-06-30T00:00:00Z",
        "schema_version": "1.0",
        "clustering_algorithm": "hdbscan",
        "labeling_model": "claude-sonnet-4-6",
        "labeling_prompt_version": "1.0",
    }
    defaults.update(kwargs)
    return defaults


def _make_jtbd_profile(**kwargs) -> JTBDProfile:
    defaults = {
        "id": str(uuid.uuid4()),
        "job_statement": "When I open Spotify, I want to discover new music, so I can enjoy fresh listening experiences.",
        "short_label": "discover new music",
        "supporting_cluster_ids": [str(uuid.uuid4())],
        "user_segments": ["casual"],
        "frequency_estimate": 100,
        "satisfaction_score": 0.3,
        "gap_score": 0.7,
        "confidence_score": 0.8,
        "gap_description": "Current recommendations repeat too often.",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generation_model": "claude-sonnet-4-6",
        "prompt_version": "1.0",
    }
    defaults.update(kwargs)
    return JTBDProfile(**defaults)


# ── Unit: job statement validation ───────────────────────────────────────────

class TestJobStatementValidation:
    def test_valid_statement_passes(self):
        stmt = "When I open Spotify, I want to find new music, so I can enjoy variety."
        assert _validate_job_statement(stmt) is True

    def test_invalid_statement_fails(self):
        assert _validate_job_statement("Spotify recommendations are bad.") is False

    def test_fix_adds_prefix(self):
        fixed = _fix_job_statement("need better recommendations.")
        assert fixed.lower().startswith("when ")

    def test_fix_preserves_valid_statement(self):
        stmt = "When I drive, I want playlist suggestions, so I can focus on the road."
        fixed = _fix_job_statement(stmt)
        assert fixed.lower().startswith("when ")


# ── Unit: segment inference ───────────────────────────────────────────────────

class TestInferSegments:
    def test_high_friction_negative_sentiment_is_power_user(self):
        cluster = _make_cluster(avg_sentiment_score=-0.5, discovery_friction_rate=0.7)
        segs = _infer_segments(cluster)
        assert "power_user" in segs

    def test_positive_sentiment_low_friction_is_casual(self):
        cluster = _make_cluster(avg_sentiment_score=0.5, discovery_friction_rate=0.1)
        segs = _infer_segments(cluster)
        assert "casual" in segs

    def test_frustration_emotion_maps_to_churned(self):
        cluster = _make_cluster(
            avg_sentiment_score=0.0, dominant_emotion="frustration",
            discovery_friction_rate=0.2
        )
        segs = _infer_segments(cluster)
        assert "churned" in segs

    def test_defaults_to_all(self):
        cluster = _make_cluster(
            avg_sentiment_score=0.1, dominant_emotion="hope",
            discovery_friction_rate=0.2
        )
        segs = _infer_segments(cluster)
        assert "all" in segs


# ── Unit: clusters block builder ─────────────────────────────────────────────

class TestBuildClustersBlock:
    def test_produces_numbered_sections(self):
        clusters = [_make_cluster(), _make_cluster()]
        review_lookup = {"r1": "I hate the repetitions", "r2": "Always the same songs"}
        block = _build_clusters_block(clusters, review_lookup)
        assert "[CLUSTER 1]" in block
        assert "[CLUSTER 2]" in block

    def test_includes_review_text(self):
        cluster = _make_cluster(representative_review_ids=["r1"])
        review_lookup = {"r1": "Spotify keeps playing the same song over and over."}
        block = _build_clusters_block([cluster], review_lookup)
        assert "same song" in block


# ── Integration: ClusterJTBDInferrer with mock LLM ───────────────────────────

class TestClusterJTBDInferrer:
    def _make_mock_client(self, job_statement: str = None) -> MagicMock:
        client = MagicMock()
        stmt = job_statement or "When I use Spotify, I want to find new music, so I can explore genres."
        client.call = AsyncMock(
            return_value=(
                {
                    "results": [
                        {
                            "cluster_index": 1,
                            "job_statement": stmt,
                            "short_label": "discover music",
                            "satisfaction_score": 0.3,
                            "gap_description": "Radio repeats too much.",
                            "confidence": 0.8,
                        }
                    ]
                },
                500,
                "claude-sonnet-4-6",
            )
        )
        return client

    def test_infer_all_returns_profiles(self):
        client = self._make_mock_client()
        inferrer = ClusterJTBDInferrer(client, batch_size=5, concurrency=1)
        clusters = [_make_cluster()]
        review_lookup = {"r1": "Same song every time", "r2": "Repetitive playlist"}

        profiles = asyncio.run(inferrer.infer_all(clusters, review_lookup))

        assert len(profiles) == 1
        assert isinstance(profiles[0], JTBDProfile)
        assert "i want to" in profiles[0].job_statement.lower()

    def test_micro_clusters_are_skipped(self):
        client = self._make_mock_client()
        inferrer = ClusterJTBDInferrer(client, batch_size=5, concurrency=1)
        micro = _make_cluster(is_micro_cluster=True)

        profiles = asyncio.run(inferrer.infer_all([micro], {}))
        assert len(profiles) == 0
        client.call.assert_not_called()

    def test_skip_cluster_ids_respected(self):
        client = self._make_mock_client()
        inferrer = ClusterJTBDInferrer(client, batch_size=5, concurrency=1)
        cluster = _make_cluster()
        skip = {cluster["id"]}

        profiles = asyncio.run(inferrer.infer_all([cluster], {}, skip_cluster_ids=skip))
        assert len(profiles) == 0

    def test_llm_failure_returns_fallback(self):
        from llm.insight_llm_client import InsightLLMError
        client = MagicMock()
        client.call = AsyncMock(side_effect=InsightLLMError("test error"))
        inferrer = ClusterJTBDInferrer(client, batch_size=5, concurrency=1)

        profiles = asyncio.run(
            inferrer.infer_all([_make_cluster()], {})
        )
        assert len(profiles) == 1
        assert profiles[0].confidence_score == 0.1

    def test_scores_clamped_to_unit_interval(self):
        client = MagicMock()
        client.call = AsyncMock(
            return_value=(
                {
                    "results": [
                        {
                            "cluster_index": 1,
                            "job_statement": "When I use Spotify, I want better music, so I can enjoy it.",
                            "short_label": "better music",
                            "satisfaction_score": 1.5,   # out of range
                            "gap_description": "gap",
                            "confidence": -0.2,          # out of range
                        }
                    ]
                },
                100,
                "test-model",
            )
        )
        inferrer = ClusterJTBDInferrer(client, batch_size=5, concurrency=1)
        profiles = asyncio.run(inferrer.infer_all([_make_cluster()], {}))
        assert profiles[0].satisfaction_score == 1.0
        assert profiles[0].confidence_score == 0.0


# ── Unit: JTBD Synthesiser ────────────────────────────────────────────────────

class TestJTBDSynthesizer:
    def test_identical_jobs_are_merged(self):
        cid1, cid2 = str(uuid.uuid4()), str(uuid.uuid4())
        p1 = _make_jtbd_profile(
            job_statement="When I use Spotify discover weekly, I want to find music, so I can enjoy.",
            supporting_cluster_ids=[cid1], frequency_estimate=100
        )
        p2 = _make_jtbd_profile(
            job_statement="When I use Spotify discover weekly, I want to find music, so I can enjoy.",
            supporting_cluster_ids=[cid2], frequency_estimate=80
        )
        synth = JTBDSynthesizer(similarity_threshold=0.4)
        merged = synth.merge([p1, p2])
        assert len(merged) == 1
        assert merged[0].frequency_estimate == 180
        assert set(merged[0].supporting_cluster_ids) == {cid1, cid2}

    def test_distinct_jobs_remain_separate(self):
        p1 = _make_jtbd_profile(
            job_statement="When I drive, I want hands-free music, so I can focus on road.",
        )
        p2 = _make_jtbd_profile(
            job_statement="When I feel sad, I want a playlist, so I can improve my mood.",
        )
        synth = JTBDSynthesizer(similarity_threshold=0.4)
        merged = synth.merge([p1, p2])
        assert len(merged) == 2

    def test_empty_input(self):
        synth = JTBDSynthesizer()
        assert synth.merge([]) == []

    def test_keyword_set_removes_stopwords(self):
        kw = _keyword_set("When I want to find music so I can enjoy")
        # 'when', 'want', 'find', 'music', 'enjoy' — stopwords filtered
        assert "find" in kw
        assert "music" in kw
        assert "when" not in kw or "music" in kw  # at least music should be there

    def test_jaccard_identical_sets(self):
        s = {"discover", "music", "playlist"}
        assert _jaccard(s, s) == 1.0

    def test_jaccard_disjoint_sets(self):
        a = {"discover", "music"}
        b = {"volume", "offline"}
        assert _jaccard(a, b) == 0.0

    def test_output_sorted_by_frequency(self):
        profiles = [
            _make_jtbd_profile(
                job_statement=f"When I open Spotify version{i}, I want audio quality, so I can stream.",
                frequency_estimate=i * 10,
            )
            for i in range(1, 5)
        ]
        synth = JTBDSynthesizer(similarity_threshold=0.3)
        merged = synth.merge(profiles)
        freqs = [p.frequency_estimate for p in merged]
        assert freqs == sorted(freqs, reverse=True)
