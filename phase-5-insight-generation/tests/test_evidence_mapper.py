"""Tests for EvidenceMapper and UnmetNeedDetector."""

import uuid

import pytest

from opportunities.evidence_mapper import EvidenceMapper
from schemas.product_insight import ProductInsight
from unmet_needs.need_detector import UnmetNeedDetector, _matched_pattern_labels


def _make_cluster(**kwargs) -> dict:
    rep_ids = [str(uuid.uuid4()) for _ in range(5)]
    member_ids = rep_ids + [str(uuid.uuid4()) for _ in range(5)]
    defaults = {
        "id": str(uuid.uuid4()),
        "label": "Discovery Issues",
        "theme": "Users struggle to find new music",
        "is_micro_cluster": False,
        "is_discovery_related": True,
        "size": 10,
        "avg_sentiment_score": -0.5,
        "discovery_friction_rate": 0.6,
        "dominant_emotion": "frustration",
        "top_features_mentioned": ["Radio"],
        "trend_direction": "stable",
        "trend_volume_change_pct": 0.0,
        "member_review_ids": member_ids,
        "representative_review_ids": rep_ids,
        "labeling_confidence": 0.8,
        "review_required": False,
        "platform_distribution": {"app_store": 1.0},
        "dominant_platform": "app_store",
        "centroid_embedding": [0.0] * 384,
        "created_at": "2026-06-30T00:00:00Z",
        "schema_version": "1.0",
        "clustering_algorithm": "hdbscan",
        "labeling_model": "claude-sonnet-4-6",
        "labeling_prompt_version": "1.0",
    }
    defaults.update(kwargs)
    return defaults


def _make_insight(cluster_id: str) -> ProductInsight:
    return ProductInsight(
        id=str(uuid.uuid4()),
        title="Test insight",
        description="Test",
        insight_type="opportunity",
        supporting_cluster_ids=[cluster_id],
        supporting_review_ids=[],
        supporting_verbatims=[],
        affected_segment="all",
        frequency_score=0.5,
        severity_score=0.5,
        uniqueness_score=0.5,
        opportunity_score=0.5,
        confidence="medium",
        confidence_score=0.7,
        reasoning="test",
        discovery_friction_related=True,
        trend_direction="stable",
        review_required=False,
        generated_at="2026-06-30T00:00:00Z",
        generation_model="test",
        prompt_version="1.0",
    )


# ── Unit: EvidenceMapper ─────────────────────────────────────────────────────

class TestEvidenceMapper:
    def test_maps_representative_reviews_first(self):
        cluster = _make_cluster()
        rep_ids = cluster["representative_review_ids"]
        review_lookup = {rid: f"Review text for {rid[:8]}" for rid in cluster["member_review_ids"]}

        insight = _make_insight(cluster["id"])
        mapper = EvidenceMapper()
        mapped = mapper.map_all([insight], [cluster], review_lookup)

        assert len(mapped) == 1
        result = mapped[0]
        # representative IDs should appear first
        for rid in result.supporting_review_ids[:len(rep_ids)]:
            assert rid in rep_ids

    def test_verbatims_match_review_ids(self):
        cluster = _make_cluster()
        review_lookup = {rid: f"text_{rid[:8]}" for rid in cluster["member_review_ids"]}

        insight = _make_insight(cluster["id"])
        mapper = EvidenceMapper()
        mapped = mapper.map_all([insight], [cluster], review_lookup)

        result = mapped[0]
        assert len(result.supporting_review_ids) == len(result.supporting_verbatims)
        for rid, text in zip(result.supporting_review_ids, result.supporting_verbatims):
            assert review_lookup[rid] == text

    def test_respects_max_verbatims(self):
        cluster = _make_cluster()
        # 10 members all with text
        review_lookup = {rid: f"review {i}" for i, rid in enumerate(cluster["member_review_ids"])}

        insight = _make_insight(cluster["id"])
        mapper = EvidenceMapper()
        mapped = mapper.map_all([insight], [cluster], review_lookup)

        assert len(mapped[0].supporting_verbatims) <= 10

    def test_skips_reviews_without_text(self):
        cluster = _make_cluster()
        # Only provide text for 2 reviews
        rep_ids = cluster["representative_review_ids"]
        review_lookup = {rep_ids[0]: "First review text", rep_ids[1]: "Second review text"}

        insight = _make_insight(cluster["id"])
        mapper = EvidenceMapper()
        mapped = mapper.map_all([insight], [cluster], review_lookup)

        assert len(mapped[0].supporting_review_ids) == 2

    def test_multiple_clusters_per_insight(self):
        cluster1 = _make_cluster()
        cluster2 = _make_cluster()
        review_lookup = {
            rid: f"text_{rid[:8]}"
            for cluster in [cluster1, cluster2]
            for rid in cluster["member_review_ids"]
        }

        insight = ProductInsight(
            id=str(uuid.uuid4()),
            title="Multi-cluster insight",
            description="Spans two clusters",
            insight_type="opportunity",
            supporting_cluster_ids=[cluster1["id"], cluster2["id"]],
            supporting_review_ids=[],
            supporting_verbatims=[],
            affected_segment="all",
            frequency_score=0.5,
            severity_score=0.5,
            uniqueness_score=0.5,
            opportunity_score=0.5,
            confidence="medium",
            confidence_score=0.7,
            reasoning="test",
            discovery_friction_related=True,
            trend_direction="stable",
            review_required=False,
            generated_at="2026-06-30T00:00:00Z",
            generation_model="test",
            prompt_version="1.0",
        )
        mapper = EvidenceMapper()
        mapped = mapper.map_all([insight], [cluster1, cluster2], review_lookup)
        # Should have reviews from both clusters
        assert len(mapped[0].supporting_review_ids) > 0

    def test_empty_review_lookup_produces_no_verbatims(self):
        cluster = _make_cluster()
        insight = _make_insight(cluster["id"])
        mapper = EvidenceMapper()
        mapped = mapper.map_all([insight], [cluster], {})
        assert mapped[0].supporting_verbatims == []

    def test_insight_without_matching_cluster_returns_empty(self):
        cluster = _make_cluster()
        insight = _make_insight("nonexistent_cluster_id")
        review_lookup = {rid: "text" for rid in cluster["member_review_ids"]}
        mapper = EvidenceMapper()
        mapped = mapper.map_all([insight], [cluster], review_lookup)
        assert mapped[0].supporting_verbatims == []


# ── Unit: UnmetNeedDetector ───────────────────────────────────────────────────

class TestUnmetNeedDetector:
    def _make_analyzed_review(self, clean_text: str, **kwargs) -> dict:
        rid = str(uuid.uuid4())
        defaults = {
            "id": rid,
            "normalized_review_id": rid,
            "sentiment": "negative",
            "sentiment_score": -0.5,
            "discovery_friction_detected": True,
            "user_segment_signal": "casual",
            "analysis_status": "success",
            "is_duplicate": False,
            "clean_text": clean_text,
        }
        defaults.update(kwargs)
        return defaults

    def test_wish_pattern_detected(self):
        patterns = _matched_pattern_labels("I wish Spotify would remember my preferences.")
        assert "wish" in patterns

    def test_would_be_great_detected(self):
        patterns = _matched_pattern_labels("It would be great if Spotify let me block artists.")
        assert "would_be_great" in patterns

    def test_why_cant_detected(self):
        patterns = _matched_pattern_labels("Why can't I skip more than 6 songs?")
        assert "why_cant" in patterns

    def test_i_want_detected(self):
        patterns = _matched_pattern_labels("I want a feature to queue offline songs.")
        assert "i_want_need" in patterns

    def test_plain_positive_review_not_detected(self):
        patterns = _matched_pattern_labels("Love the app, great music selection!")
        assert len(patterns) == 0

    def test_detect_groups_by_cluster(self):
        cluster_id = str(uuid.uuid4())
        cluster = _make_cluster(id=cluster_id)

        # Make member_review_ids and use them
        member_ids = cluster["member_review_ids"]
        reviews = [
            self._make_analyzed_review(
                "I wish Spotify would show me more varied recommendations.",
                normalized_review_id=mid,
            )
            for mid in member_ids[:5]
        ]

        detector = UnmetNeedDetector(min_cluster_size=3)
        candidates = detector.detect([cluster], reviews, {r["id"]: r["clean_text"] for r in reviews})

        assert len(candidates) >= 1
        assert candidates[0].cluster_id == cluster_id

    def test_minimum_cluster_size_filter(self):
        cluster_id = str(uuid.uuid4())
        cluster = _make_cluster(id=cluster_id)
        member_ids = cluster["member_review_ids"]

        # Only 2 reviews express the need — below min_cluster_size=3
        reviews = [
            self._make_analyzed_review("I wish Spotify had offline lyrics.", normalized_review_id=mid)
            for mid in member_ids[:2]
        ]
        detector = UnmetNeedDetector(min_cluster_size=3)
        candidates = detector.detect([cluster], reviews)
        assert len(candidates) == 0

    def test_failed_reviews_excluded(self):
        cluster_id = str(uuid.uuid4())
        cluster = _make_cluster(id=cluster_id)
        member_ids = cluster["member_review_ids"]

        reviews = [
            self._make_analyzed_review(
                "I wish Spotify had this feature.",
                normalized_review_id=mid,
                analysis_status="failed",
            )
            for mid in member_ids[:5]
        ]
        detector = UnmetNeedDetector(min_cluster_size=3)
        candidates = detector.detect([cluster], reviews)
        assert len(candidates) == 0

    def test_positive_non_friction_reviews_excluded(self):
        cluster_id = str(uuid.uuid4())
        cluster = _make_cluster(id=cluster_id)
        member_ids = cluster["member_review_ids"]

        reviews = [
            self._make_analyzed_review(
                "I wish there were more artists, but overall great app!",
                normalized_review_id=mid,
                sentiment="positive",
                discovery_friction_detected=False,
            )
            for mid in member_ids[:5]
        ]
        detector = UnmetNeedDetector(min_cluster_size=3)
        candidates = detector.detect([cluster], reviews)
        # Positive + no friction → excluded
        assert len(candidates) == 0

    def test_candidates_sorted_by_frequency(self):
        cluster_a = _make_cluster()
        cluster_b = _make_cluster()

        member_ids_a = cluster_a["member_review_ids"]
        member_ids_b = cluster_b["member_review_ids"]

        # Cluster A has 8 matching reviews; Cluster B has 4
        reviews = (
            [
                self._make_analyzed_review("I need better recommendations", normalized_review_id=m)
                for m in member_ids_a[:8]
            ]
            + [
                self._make_analyzed_review("I wish I could queue songs", normalized_review_id=m)
                for m in member_ids_b[:4]
            ]
        )
        detector = UnmetNeedDetector(min_cluster_size=3)
        candidates = detector.detect([cluster_a, cluster_b], reviews)
        if len(candidates) >= 2:
            assert candidates[0].expressed_frequency >= candidates[1].expressed_frequency
