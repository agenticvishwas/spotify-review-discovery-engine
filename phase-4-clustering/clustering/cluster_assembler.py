"""Assembles ReviewCluster dicts from grouped review records and full embeddings."""

import logging
import uuid
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

MIN_CLUSTER_SIZE_FOR_INSIGHT = 5


@dataclass
class ReviewRecord:
    """Fields needed by Phase 4 from a joined AnalyzedReview + NormalizedReview."""
    review_id: str
    embedding: np.ndarray          # 384-dim full embedding (not UMAP-reduced)
    platform: str
    published_at: str              # ISO8601 — used for trend analysis
    sentiment_score: float
    discovery_friction_detected: bool
    emotion_tags: list[str] = field(default_factory=list)
    feature_mentions: list[str] = field(default_factory=list)


class ClusterAssembler:
    """Builds a ReviewCluster dict for each group of records sharing a cluster label."""

    def build(self, records: list[ReviewRecord]) -> dict:
        """Build a partial ReviewCluster dict (label/theme/trend filled downstream)."""
        review_ids = [r.review_id for r in records]
        embeddings = np.vstack([r.embedding for r in records])
        centroid = embeddings.mean(axis=0)

        rep_ids = self._representative_ids(review_ids, embeddings, centroid, n=5)

        avg_sentiment = float(np.mean([r.sentiment_score for r in records]))
        friction_rate = sum(1 for r in records if r.discovery_friction_detected) / len(records)

        platform_counts: Counter = Counter(r.platform for r in records)
        total = len(records)
        platform_dist = {p: round(c / total, 4) for p, c in platform_counts.items()}
        dominant_platform = platform_counts.most_common(1)[0][0]

        all_emotions: list[str] = []
        for r in records:
            all_emotions.extend(r.emotion_tags)
        dominant_emotion = Counter(all_emotions).most_common(1)[0][0] if all_emotions else "unknown"

        all_features: list[str] = []
        for r in records:
            all_features.extend(r.feature_mentions)
        top_features = [f for f, _ in Counter(all_features).most_common(10)]

        return {
            "id": str(uuid.uuid4()),
            "label": "",
            "theme": "",
            "is_discovery_related": False,
            "member_review_ids": review_ids,
            "representative_review_ids": rep_ids,
            "centroid_embedding": centroid.tolist(),
            "size": len(records),
            "avg_sentiment_score": round(avg_sentiment, 4),
            "discovery_friction_rate": round(friction_rate, 4),
            "dominant_platform": dominant_platform,
            "platform_distribution": platform_dist,
            "dominant_emotion": dominant_emotion,
            "top_features_mentioned": top_features,
            "trend_direction": "stable",
            "trend_volume_change_pct": 0.0,
            "is_micro_cluster": len(records) < MIN_CLUSTER_SIZE_FOR_INSIGHT,
            "labeling_confidence": 0.0,
            "review_required": False,
        }

    @staticmethod
    def _representative_ids(
        review_ids: list[str],
        embeddings: np.ndarray,
        centroid: np.ndarray,
        n: int = 5,
    ) -> list[str]:
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        safe_norms = np.where(norms == 0, 1.0, norms)
        normed = embeddings / safe_norms
        normed_centroid = centroid / (np.linalg.norm(centroid) or 1.0)
        sims = normed @ normed_centroid
        top_idx = np.argsort(-sims)[:n]
        return [review_ids[i] for i in top_idx]

    def build_all(
        self,
        records: list[ReviewRecord],
        labels: np.ndarray,
    ) -> list[dict]:
        """Build one cluster dict per unique label."""
        from collections import defaultdict
        groups: dict[int, list[ReviewRecord]] = defaultdict(list)
        for record, label in zip(records, labels):
            groups[int(label)].append(record)

        clusters = []
        for label in sorted(groups):
            group_records = groups[label]
            cluster = self.build(group_records)
            clusters.append(cluster)
            logger.debug(
                "phase=4 action=assemble_cluster label=%d size=%d",
                label, len(group_records),
            )

        logger.info("phase=4 action=assemble_complete clusters=%d", len(clusters))
        return clusters
