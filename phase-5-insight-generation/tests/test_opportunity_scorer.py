"""Tests for OpportunityScorer."""

import uuid

import pytest

from opportunities.opportunity_scorer import OpportunityScorer, _derive_affected_segment, _confidence_level
from opportunities.opportunity_ranker import OpportunityRanker
from schemas.product_insight import ProductInsight


def _make_cluster(**kwargs) -> dict:
    defaults = {
        "id": str(uuid.uuid4()),
        "label": "Repetitive Algorithm",
        "theme": "Users see same songs repeatedly",
        "is_micro_cluster": False,
        "is_discovery_related": True,
        "size": 100,
        "avg_sentiment_score": -0.6,
        "discovery_friction_rate": 0.7,
        "dominant_emotion": "frustration",
        "top_features_mentioned": ["Radio", "Discover Weekly"],
        "trend_direction": "increasing",
        "trend_volume_change_pct": 20.0,
        "member_review_ids": [str(uuid.uuid4()) for _ in range(10)],
        "representative_review_ids": [str(uuid.uuid4()) for _ in range(5)],
        "labeling_confidence": 0.85,
        "review_required": False,
        "platform_distribution": {"app_store": 0.6},
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


# ── Unit: scoring formula ─────────────────────────────────────────────────────

class TestOpportunityScorerFormula:
    def test_all_scores_in_unit_interval(self):
        scorer = OpportunityScorer()
        clusters = [_make_cluster() for _ in range(3)]
        insights = scorer.score_all(clusters, total_reviews=1000)

        for ins in insights:
            assert 0.0 <= ins.frequency_score <= 1.0
            assert 0.0 <= ins.severity_score <= 1.0
            assert 0.0 <= ins.uniqueness_score <= 1.0
            assert 0.0 <= ins.opportunity_score <= 1.0
            assert 0.0 <= ins.confidence_score <= 1.0

    def test_larger_cluster_has_higher_frequency_score(self):
        scorer = OpportunityScorer()
        big = _make_cluster(size=500)
        small = _make_cluster(size=50)
        insights = scorer.score_all([big, small], total_reviews=1000)

        by_id = {ins.supporting_cluster_ids[0]: ins for ins in insights}
        assert by_id[big["id"]].frequency_score > by_id[small["id"]].frequency_score

    def test_negative_sentiment_drives_severity(self):
        scorer = OpportunityScorer()
        negative = _make_cluster(avg_sentiment_score=-0.9)
        positive = _make_cluster(avg_sentiment_score=0.9)
        insights = scorer.score_all([negative, positive], total_reviews=1000)

        by_id = {ins.supporting_cluster_ids[0]: ins for ins in insights}
        assert by_id[negative["id"]].severity_score > by_id[positive["id"]].severity_score

    def test_smaller_cluster_has_higher_uniqueness(self):
        scorer = OpportunityScorer()
        big = _make_cluster(size=800)
        small = _make_cluster(size=10)
        insights = scorer.score_all([big, small], total_reviews=1000)

        by_id = {ins.supporting_cluster_ids[0]: ins for ins in insights}
        assert by_id[small["id"]].uniqueness_score > by_id[big["id"]].uniqueness_score

    def test_micro_clusters_excluded(self):
        scorer = OpportunityScorer()
        micro = _make_cluster(is_micro_cluster=True)
        normal = _make_cluster()
        insights = scorer.score_all([micro, normal], total_reviews=1000)
        assert len(insights) == 1
        assert insights[0].supporting_cluster_ids[0] == normal["id"]

    def test_empty_clusters(self):
        scorer = OpportunityScorer()
        insights = scorer.score_all([], total_reviews=0)
        assert insights == []

    def test_zero_total_reviews(self):
        scorer = OpportunityScorer()
        insights = scorer.score_all([_make_cluster()], total_reviews=0)
        assert insights == []

    def test_review_required_flag_when_low_labeling_confidence(self):
        scorer = OpportunityScorer()
        cluster = _make_cluster(labeling_confidence=0.3, review_required=True)
        insights = scorer.score_all([cluster], total_reviews=1000)
        # review_required=True because low confidence_score < 0.6
        assert any(ins.review_required for ins in insights)

    def test_jtbd_cluster_map_sets_title(self):
        scorer = OpportunityScorer()
        cluster = _make_cluster()
        jtbd_map = {cluster["id"]: "Find New Music"}
        insights = scorer.score_all([cluster], total_reviews=1000, jtbd_cluster_map=jtbd_map)
        assert insights[0].title == "Find New Music"


# ── Unit: confidence level ────────────────────────────────────────────────────

class TestConfidenceLevel:
    def test_high_confidence(self):
        assert _confidence_level(0.8) == "high"

    def test_medium_confidence(self):
        assert _confidence_level(0.6) == "medium"

    def test_low_confidence(self):
        assert _confidence_level(0.3) == "low"


# ── Unit: segment derivation ──────────────────────────────────────────────────

class TestDeriveAffectedSegment:
    def test_high_friction_negative_is_power_user(self):
        cluster = _make_cluster(avg_sentiment_score=-0.5, discovery_friction_rate=0.6)
        assert _derive_affected_segment(cluster) == "power_user"

    def test_high_negative_frustration_is_churned(self):
        cluster = _make_cluster(avg_sentiment_score=-0.4, dominant_emotion="frustration", discovery_friction_rate=0.2)
        assert _derive_affected_segment(cluster) == "churned"

    def test_positive_low_friction_is_casual(self):
        cluster = _make_cluster(avg_sentiment_score=0.5, discovery_friction_rate=0.1)
        assert _derive_affected_segment(cluster) == "casual"

    def test_neutral_defaults_to_all(self):
        cluster = _make_cluster(avg_sentiment_score=0.0, discovery_friction_rate=0.2, dominant_emotion="neutral")
        assert _derive_affected_segment(cluster) == "all"


# ── Integration: Ranker ───────────────────────────────────────────────────────

class TestOpportunityRanker:
    def _make_insight(self, opp_score: float, review_required: bool = False) -> ProductInsight:
        return ProductInsight(
            id=str(uuid.uuid4()),
            title="Test insight",
            description="Test",
            insight_type="opportunity",
            supporting_cluster_ids=[str(uuid.uuid4())],
            supporting_review_ids=["r1", "r2", "r3"],
            supporting_verbatims=["v1", "v2", "v3"],
            affected_segment="all",
            frequency_score=opp_score,
            severity_score=0.5,
            uniqueness_score=0.5,
            opportunity_score=opp_score,
            confidence="high" if opp_score > 0.6 else "medium",
            confidence_score=opp_score,
            reasoning="test",
            discovery_friction_related=True,
            trend_direction="stable",
            review_required=review_required,
            generated_at="2026-06-30T00:00:00Z",
            generation_model="test",
            prompt_version="1.0",
        )

    def test_main_feed_sorted_by_opp_score(self):
        insights = [self._make_insight(opp) for opp in [0.3, 0.8, 0.5]]
        ranker = OpportunityRanker()
        result = ranker.rank(insights)

        scores = [i.opportunity_score for i in result.main_feed]
        assert scores == sorted(scores, reverse=True)

    def test_review_required_goes_to_pending(self):
        main_ins = self._make_insight(0.8, review_required=False)
        pending_ins = self._make_insight(0.7, review_required=True)
        ranker = OpportunityRanker()
        result = ranker.rank([main_ins, pending_ins])

        assert main_ins in result.main_feed
        assert pending_ins in result.pending_review
        assert main_ins not in result.pending_review

    def test_all_ranked_is_main_plus_pending(self):
        insights = [self._make_insight(0.5, r) for r in [False, True, False]]
        ranker = OpportunityRanker()
        result = ranker.rank(insights)

        assert len(result.all_ranked) == 3
        assert result.all_ranked[:len(result.main_feed)] == result.main_feed

    def test_empty_input(self):
        ranker = OpportunityRanker()
        result = ranker.rank([])
        assert result.main_feed == []
        assert result.pending_review == []
        assert result.all_ranked == []
