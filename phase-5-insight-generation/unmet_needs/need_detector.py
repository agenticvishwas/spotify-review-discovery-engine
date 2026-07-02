"""Pattern-based unmet need detection — no LLM required.

Scans AnalyzedReview texts for linguistic markers that indicate unfulfilled
desires. Groups matching reviews by their cluster membership so that the
synthesiser can formulate one need statement per cluster group.

Detection criteria (all three must be true for a review to be flagged):
  1. Contains at least one desire pattern (wish, want, need, etc.)
  2. Sentiment is negative or mixed  OR  discovery_friction_detected is True
  3. The review is not a duplicate and passed quality filtering

This is a cheap O(n) pass with no API calls.
"""

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

# Linguistic patterns indicating an unmet desire
_DESIRE_PATTERNS: list[re.Pattern] = [
    re.compile(r"\bwish\b", re.IGNORECASE),
    re.compile(r"\bshould\b.{0,30}\b(be able|have|let|allow)\b", re.IGNORECASE),
    re.compile(r"\bwould be (great|nice|helpful|amazing|better)\b", re.IGNORECASE),
    re.compile(r"\bwhy (can'?t|doesn'?t|won'?t)\b", re.IGNORECASE),
    re.compile(r"\bif only\b", re.IGNORECASE),
    re.compile(r"\bI (want|need|wish|expect)\b", re.IGNORECASE),
    re.compile(r"\bplease (add|fix|give|let|make|allow)\b", re.IGNORECASE),
    re.compile(r"\bmissing\b.{0,30}\bfeature\b", re.IGNORECASE),
    re.compile(r"\bcan'?t\b.{0,30}\b(find|discover|get|access|use)\b", re.IGNORECASE),
    re.compile(r"\bneed (a|an|the|to)\b", re.IGNORECASE),
    re.compile(r"\bwant (a|an|the|to)\b", re.IGNORECASE),
]

_NEGATIVE_SENTIMENTS = frozenset(["negative", "mixed"])


@dataclass
class RawNeedCandidate:
    """A group of reviews from the same cluster expressing a similar unmet need."""

    cluster_id: str
    cluster_label: str
    cluster_theme: str
    affected_segment: str
    sample_review_ids: list[str] = field(default_factory=list)
    sample_texts: list[str] = field(default_factory=list)
    matched_patterns: list[str] = field(default_factory=list)
    expressed_frequency: int = 0


def _matched_pattern_labels(text: str) -> list[str]:
    labels: list[str] = []
    pattern_labels = [
        "wish", "should_be_able", "would_be_great", "why_cant",
        "if_only", "i_want_need", "please_add_fix", "missing_feature",
        "cant_find_discover", "need_a", "want_a",
    ]
    for pattern, label in zip(_DESIRE_PATTERNS, pattern_labels):
        if pattern.search(text):
            labels.append(label)
    return labels


def _is_negative_or_friction(review: dict) -> bool:
    return (
        review.get("sentiment", "") in _NEGATIVE_SENTIMENTS
        or review.get("discovery_friction_detected", False)
    )


def _review_is_eligible(review: dict) -> bool:
    if review.get("analysis_status") == "failed":
        return False
    if review.get("is_duplicate"):
        return False
    if not review.get("clean_text", "").strip():
        return False
    return True


class UnmetNeedDetector:
    """Scans AnalyzedReview records for expressed but unfulfilled needs.

    Usage:
        detector = UnmetNeedDetector(min_cluster_size=3)
        candidates = detector.detect(clusters, analyzed_reviews, review_lookup)
    """

    def __init__(self, min_cluster_size: int = 3, max_samples_per_cluster: int = 10):
        self._min_cluster_size = min_cluster_size
        self._max_samples = max_samples_per_cluster

    def detect(
        self,
        clusters: list[dict],
        analyzed_reviews: list[dict],
        review_text_lookup: Optional[dict[str, str]] = None,
    ) -> list[RawNeedCandidate]:
        """Detect unmet need candidates.

        Args:
            clusters: ReviewCluster dicts from Phase 4
            analyzed_reviews: AnalyzedReview dicts from Phase 3
            review_text_lookup: {review_id → clean_text} (optional; used for
                                 enriching sample_texts field)

        Returns:
            list of RawNeedCandidate (one per cluster that has enough matches)
        """
        cluster_map: dict[str, dict] = {c["id"]: c for c in clusters}
        review_text_lookup = review_text_lookup or {}

        # Build a reverse lookup: review_id → cluster_id
        review_to_cluster: dict[str, str] = {}
        for cluster in clusters:
            for rid in cluster.get("member_review_ids", []):
                review_to_cluster[rid] = cluster["id"]

        # Group flagged reviews by cluster
        cluster_buckets: dict[str, list[dict]] = defaultdict(list)
        for review in analyzed_reviews:
            if not _review_is_eligible(review):
                continue
            if not _is_negative_or_friction(review):
                continue
            text = review_text_lookup.get(review.get("id", "")) or review.get("clean_text", "")
            if not text:
                continue
            patterns = _matched_pattern_labels(text)
            if not patterns:
                continue

            cluster_id = review_to_cluster.get(review.get("normalized_review_id", ""))
            if not cluster_id:
                # Try to find cluster via normalized_review_id → id mismatch
                # Phase 3 output uses 'id' for the analyzed review id
                cluster_id = review_to_cluster.get(review.get("id", ""))
            if not cluster_id:
                continue

            cluster_buckets[cluster_id].append({
                "review": review,
                "text": text,
                "patterns": patterns,
            })

        candidates: list[RawNeedCandidate] = []
        for cluster_id, matches in cluster_buckets.items():
            if len(matches) < self._min_cluster_size:
                continue

            cluster = cluster_map.get(cluster_id, {})
            if cluster.get("is_micro_cluster"):
                continue

            # Collect unique pattern labels
            all_patterns: list[str] = []
            for m in matches:
                for p in m["patterns"]:
                    if p not in all_patterns:
                        all_patterns.append(p)

            # Sample up to max_samples review IDs and texts
            sample_matches = matches[: self._max_samples]
            sample_ids: list[str] = []
            sample_texts: list[str] = []
            for m in sample_matches:
                rid = m["review"].get("id", "")
                if rid:
                    sample_ids.append(rid)
                if m["text"]:
                    sample_texts.append(m["text"][:250])

            # Determine affected segment from dominant user_segment_signal
            seg_counter: dict[str, int] = defaultdict(int)
            for m in matches:
                seg_counter[m["review"].get("user_segment_signal", "unknown")] += 1
            affected_seg = max(seg_counter, key=seg_counter.get) if seg_counter else "all"

            candidates.append(
                RawNeedCandidate(
                    cluster_id=cluster_id,
                    cluster_label=cluster.get("label", ""),
                    cluster_theme=cluster.get("theme", ""),
                    affected_segment=affected_seg,
                    sample_review_ids=sample_ids,
                    sample_texts=sample_texts,
                    matched_patterns=all_patterns,
                    expressed_frequency=len(matches),
                )
            )

        candidates.sort(key=lambda c: c.expressed_frequency, reverse=True)
        return candidates
