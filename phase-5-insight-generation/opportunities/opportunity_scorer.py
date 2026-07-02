"""Deterministic opportunity scoring — no LLM required.

Scoring formula (from the Phase 5 spec):
  frequency_score  = cluster.size / total_reviews
  severity_score   = abs(cluster.avg_sentiment_score) when avg < 0, else 0
  uniqueness_score = 1 - (cluster.size / largest_cluster_size)
  opportunity_score = (frequency * 0.4) + (severity * 0.4) + (uniqueness * 0.2)

All scores are clamped to [0, 1].

The scorer also generates one ProductInsight per scored cluster, with
supporting_cluster_ids, affected_segment, and trend_direction populated
from cluster metadata. Evidence linking (verbatims) is handled separately
by EvidenceMapper.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from schemas.product_insight import ProductInsight

logger = logging.getLogger(__name__)

_CONFIDENCE_HIGH = 0.75
_CONFIDENCE_MEDIUM = 0.50
_REVIEW_REQUIRED_THRESHOLD = 0.60


def _confidence_level(score: float) -> str:
    if score >= _CONFIDENCE_HIGH:
        return "high"
    if score >= _CONFIDENCE_MEDIUM:
        return "medium"
    return "low"


def _derive_affected_segment(cluster: dict) -> str:
    """Heuristic segment derivation from cluster signals."""
    sentiment = cluster.get("avg_sentiment_score", 0.0)
    friction = cluster.get("discovery_friction_rate", 0.0)
    emotion = cluster.get("dominant_emotion", "")

    if sentiment < -0.4 and friction > 0.5:
        return "power_user"
    if sentiment < -0.3 and emotion in ("frustration", "disappointment"):
        return "churned"
    if sentiment > 0.3 and friction < 0.2:
        return "casual"
    return "all"


class OpportunityScorer:
    """Scores each cluster as a product opportunity and builds ProductInsight objects.

    The confidence_score for each insight is derived from cluster metadata:
    labeling_confidence × (1 - noise_penalty). Insights with confidence < 0.6
    are marked review_required=True so PMs can inspect them separately.
    """

    def score_all(
        self,
        clusters: list[dict],
        total_reviews: int,
        jtbd_cluster_map: Optional[dict[str, str]] = None,
        model_name: str = "deterministic",
        prompt_version: str = "n/a",
    ) -> list[ProductInsight]:
        """Score all eligible clusters as product opportunities.

        Args:
            clusters: ReviewCluster dicts from Phase 4
            total_reviews: total number of reviews in the corpus (denominator)
            jtbd_cluster_map: {cluster_id → short_label} from JTBD inference
            model_name: model that labelled the clusters (for lineage)
            prompt_version: prompt version used in labelling phase

        Returns:
            list of ProductInsight (unsorted — ranking done by OpportunityRanker)
        """
        eligible = [c for c in clusters if not c.get("is_micro_cluster")]
        if not eligible or total_reviews == 0:
            return []

        largest_size = max(c.get("size", 1) for c in eligible)
        now = datetime.now(timezone.utc).isoformat()
        jtbd_map = jtbd_cluster_map or {}
        insights: list[ProductInsight] = []

        for cluster in eligible:
            size = cluster.get("size", 0)
            avg_sentiment = cluster.get("avg_sentiment_score", 0.0)
            friction_rate = cluster.get("discovery_friction_rate", 0.0)
            labeling_conf = cluster.get("labeling_confidence", 0.7)
            trend = cluster.get("trend_direction", "stable")
            is_discovery = cluster.get("is_discovery_related", False)

            # --- Core scoring ------------------------------------------------
            freq_score = round(min(size / total_reviews, 1.0), 4)

            # Severity: only negative sentiment counts as "pain"
            if avg_sentiment < 0:
                sev_score = round(min(abs(avg_sentiment), 1.0), 4)
            else:
                sev_score = round(friction_rate * 0.5, 4)  # friction is a softer severity signal

            # Uniqueness: small cluster = niche = unique need
            uniq_score = round(1.0 - (size / largest_size), 4)

            opp_score = round(
                (freq_score * 0.4) + (sev_score * 0.4) + (uniq_score * 0.2), 4
            )
            opp_score = max(0.0, min(1.0, opp_score))

            # Confidence = labeling quality × penalised by review_required flag
            confidence_score = round(labeling_conf * (0.8 if cluster.get("review_required") else 1.0), 4)
            confidence_score = max(0.0, min(1.0, confidence_score))

            # Build title from JTBD label or cluster label
            jtbd_label = jtbd_map.get(cluster["id"], "")
            title = jtbd_label or cluster.get("label", "Unlabelled cluster")

            # Determine insight type
            if avg_sentiment < -0.2 and friction_rate > 0.3:
                insight_type = "problem"
            elif jtbd_label:
                insight_type = "jtbd"
            elif friction_rate > 0.4:
                insight_type = "unmet_need"
            else:
                insight_type = "opportunity"

            insights.append(
                ProductInsight(
                    id=str(uuid.uuid4()),
                    title=title,
                    description=cluster.get("theme", ""),
                    insight_type=insight_type,
                    supporting_cluster_ids=[cluster["id"]],
                    supporting_review_ids=[],       # filled by EvidenceMapper
                    supporting_verbatims=[],         # filled by EvidenceMapper
                    affected_segment=_derive_affected_segment(cluster),
                    frequency_score=freq_score,
                    severity_score=sev_score,
                    uniqueness_score=uniq_score,
                    opportunity_score=opp_score,
                    confidence=_confidence_level(confidence_score),
                    confidence_score=confidence_score,
                    reasoning=(
                        f"Cluster size {size} ({freq_score:.1%} of corpus). "
                        f"Avg sentiment {avg_sentiment:.2f}. "
                        f"Discovery friction {friction_rate:.0%}. "
                        f"Trend: {trend}."
                    ),
                    discovery_friction_related=is_discovery,
                    trend_direction=trend,
                    review_required=confidence_score < _REVIEW_REQUIRED_THRESHOLD,
                    generated_at=now,
                    generation_model=model_name,
                    prompt_version=prompt_version,
                )
            )

        logger.info("scorer=complete insights=%d eligible_clusters=%d", len(insights), len(eligible))
        return insights
