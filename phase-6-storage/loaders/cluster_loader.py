from __future__ import annotations
import json
import logging
from .base_loader import BaseLoader

logger = logging.getLogger(__name__)


class ClusterLoader(BaseLoader):
    def load_all(self) -> tuple[list[dict], int]:
        clusters: list[dict] = []
        members: list[dict] = []  # (cluster_id, review_id, is_representative)
        skipped = 0

        for raw in self._iter_jsonl():
            if not raw.get("id"):
                skipped += 1
                continue

            cluster_id = raw["id"]
            representative_ids = set(raw.get("representative_review_ids", []))

            clusters.append({
                "id": cluster_id,
                "label": raw.get("label", "Unlabeled"),
                "theme": raw.get("theme", ""),
                "is_discovery_related": int(bool(raw.get("is_discovery_related", False))),
                "size": raw.get("size", 0),
                "avg_sentiment_score": raw.get("avg_sentiment_score"),
                "discovery_friction_rate": raw.get("discovery_friction_rate"),
                "dominant_platform": raw.get("dominant_platform"),
                "platform_distribution": json.dumps(raw.get("platform_distribution", {})),
                "dominant_emotion": raw.get("dominant_emotion"),
                "top_features_mentioned": json.dumps(raw.get("top_features_mentioned", [])),
                "trend_direction": raw.get("trend_direction"),
                "trend_volume_change_pct": raw.get("trend_volume_change_pct"),
                "is_micro_cluster": int(bool(raw.get("is_micro_cluster", False))),
                "labeling_confidence": raw.get("labeling_confidence"),
                "review_required": int(bool(raw.get("review_required", False))),
                "clustering_algorithm": raw.get("clustering_algorithm", "hdbscan"),
                "labeling_model": raw.get("labeling_model"),
                "labeling_prompt_version": raw.get("labeling_prompt_version"),
                "created_at": raw.get("created_at", ""),
                "schema_version": raw.get("schema_version", "1.0"),
            })

            for review_id in raw.get("member_review_ids", []):
                members.append({
                    "cluster_id": cluster_id,
                    "review_id": review_id,
                    "is_representative": int(review_id in representative_ids),
                })

        logger.info(
            "Cluster loader: %d clusters, %d member rows, %d skipped",
            len(clusters), len(members), skipped,
        )
        return clusters, members, skipped  # type: ignore[return-value]
