"""Evidence mapping — links ProductInsights to verbatim review quotes.

For each insight, selects the 3–10 representative reviews from its cluster
and populates supporting_review_ids and supporting_verbatims.

Selection strategy:
  1. Use the cluster's representative_review_ids (already ranked by centrality
     in Phase 4) as the primary source.
  2. Fall back to the first N member_review_ids if representative list is small.
  3. Only include reviews whose text is available in the lookup dict.

This is a pure data-linking operation — no LLM call required.
"""

import logging
from typing import Optional

from schemas.product_insight import ProductInsight

logger = logging.getLogger(__name__)

_MIN_VERBATIMS = 3
_MAX_VERBATIMS = 10


class EvidenceMapper:
    """Attaches verbatim review quotes to ProductInsight objects."""

    def map_all(
        self,
        insights: list[ProductInsight],
        clusters: list[dict],
        review_text_lookup: dict[str, str],
    ) -> list[ProductInsight]:
        """Add supporting_review_ids and supporting_verbatims to each insight.

        Args:
            insights: ProductInsight objects (supporting fields currently empty)
            clusters: ReviewCluster dicts (provides representative_review_ids)
            review_text_lookup: {review_id → clean_text}

        Returns:
            New list of ProductInsight objects with evidence fields populated.
        """
        cluster_map: dict[str, dict] = {c["id"]: c for c in clusters}
        mapped: list[ProductInsight] = []

        for insight in insights:
            review_ids, verbatims = self._pick_evidence(
                insight.supporting_cluster_ids, cluster_map, review_text_lookup
            )
            # Pydantic models are frozen — create a new instance with evidence
            mapped.append(
                insight.model_copy(
                    update={
                        "supporting_review_ids": review_ids,
                        "supporting_verbatims": verbatims,
                    }
                )
            )

        insufficient = sum(
            1 for m in mapped if len(m.supporting_review_ids) < _MIN_VERBATIMS
        )
        if insufficient:
            logger.warning(
                "evidence=below_minimum count=%d min=%d", insufficient, _MIN_VERBATIMS
            )

        logger.info(
            "evidence=mapped insights=%d avg_verbatims=%.1f",
            len(mapped),
            sum(len(m.supporting_verbatims) for m in mapped) / max(len(mapped), 1),
        )
        return mapped

    def _pick_evidence(
        self,
        cluster_ids: list[str],
        cluster_map: dict[str, dict],
        review_text_lookup: dict[str, str],
    ) -> tuple[list[str], list[str]]:
        """Gather representative review IDs and their text for one insight."""
        candidate_ids: list[str] = []

        for cid in cluster_ids:
            cluster = cluster_map.get(cid)
            if not cluster:
                continue
            # Prioritise representative (centroid-closest) reviews
            rep_ids = cluster.get("representative_review_ids", [])
            candidate_ids.extend(rid for rid in rep_ids if rid not in candidate_ids)
            # Back-fill from full member list if needed
            if len(candidate_ids) < _MAX_VERBATIMS:
                for rid in cluster.get("member_review_ids", []):
                    if rid not in candidate_ids:
                        candidate_ids.append(rid)
                    if len(candidate_ids) >= _MAX_VERBATIMS * 2:
                        break

        # Keep only reviews with text in the lookup
        selected_ids: list[str] = []
        verbatims: list[str] = []
        for rid in candidate_ids:
            text = review_text_lookup.get(rid, "").strip()
            if text:
                selected_ids.append(rid)
                verbatims.append(text[:500])
            if len(selected_ids) >= _MAX_VERBATIMS:
                break

        return selected_ids, verbatims
