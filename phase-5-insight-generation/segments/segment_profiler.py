"""User segment profiling from AnalyzedReview signals.

Approach
────────
1. Group AnalyzedReview records by `user_segment_signal` — deterministic, no LLM.
2. Compute per-segment statistics in pure Python (counts, rates, top terms).
3. Make ONE LLM call per segment to generate the behavioural description,
   primary_jtbd, and primary_pain. This costs at most 5 LLM calls total
   (one per known segment type) regardless of corpus size.
"""

import asyncio
import json
import logging
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from llm.insight_llm_client import InsightLLMClient, InsightLLMError
from schemas.product_insight import UserSegment

logger = logging.getLogger(__name__)

_PROMPT_DIR = Path(__file__).parent / "prompts"
CURRENT_PROMPT_VERSION = "1.0"

KNOWN_SEGMENTS = ("power_user", "casual", "new", "churned", "unknown")
_MIN_SEGMENT_REVIEWS = 5   # skip segments with fewer than this many reviews


def _load_prompt(version: str, provider: str) -> dict:
    specific = _PROMPT_DIR / f"segment_description_v{version}_{provider}.json"
    if specific.exists():
        return json.loads(specific.read_text(encoding="utf-8"))
    generic = _PROMPT_DIR / f"segment_description_v{version}.json"
    return json.loads(generic.read_text(encoding="utf-8"))


def _top_n(counter: Counter, n: int = 5) -> list[str]:
    return [item for item, _ in counter.most_common(n) if item]


class SegmentProfiler:
    """Builds UserSegment profiles for each user_segment_signal group."""

    def __init__(
        self,
        llm_client: InsightLLMClient,
        prompt_version: str = CURRENT_PROMPT_VERSION,
        provider_name: str = "anthropic",
    ):
        self._client = llm_client
        self._prompt_cfg = _load_prompt(prompt_version, provider_name)
        self._prompt_version = prompt_version

    async def profile_all(
        self,
        analyzed_reviews: list[dict],
        total_reviews: Optional[int] = None,
    ) -> list[UserSegment]:
        """Build one UserSegment per segment type found in analyzed_reviews.

        Args:
            analyzed_reviews: AnalyzedReview dicts from Phase 3 JSONL
            total_reviews: denominator for fraction_of_total (defaults to len)
        """
        total = total_reviews or len(analyzed_reviews)
        if total == 0:
            return []

        # Group by segment
        groups: dict[str, list[dict]] = {s: [] for s in KNOWN_SEGMENTS}
        for review in analyzed_reviews:
            seg = review.get("user_segment_signal", "unknown")
            if seg not in groups:
                seg = "unknown"
            groups[seg].append(review)

        # Build profile concurrently for each segment that has enough reviews
        tasks = []
        segment_labels = []
        for seg_label, reviews in groups.items():
            if len(reviews) >= _MIN_SEGMENT_REVIEWS:
                stats = _compute_stats(reviews, total)
                tasks.append(self._profile_segment(seg_label, reviews, stats, total))
                segment_labels.append(seg_label)

        if not tasks:
            logger.warning("segments=no_eligible_segments total=%d", total)
            return []

        results = await asyncio.gather(*tasks, return_exceptions=True)
        segments: list[UserSegment] = []
        for label, result in zip(segment_labels, results):
            if isinstance(result, Exception):
                logger.error("segment=%s profiling_failed error=%s", label, result)
            else:
                if result is not None:
                    segments.append(result)

        logger.info("segments=complete count=%d", len(segments))
        return segments

    async def _profile_segment(
        self,
        segment_label: str,
        reviews: list[dict],
        stats: dict,
        total: int,
    ) -> Optional[UserSegment]:
        prompt_cfg = self._prompt_cfg
        user_message = prompt_cfg["user_template"].format(
            segment_label=segment_label,
            review_count=stats["count"],
            fraction_pct=round(stats["fraction"] * 100, 1),
            avg_sentiment=stats["avg_sentiment"],
            friction_rate=stats["friction_rate"],
            platform=stats["dominant_platform"],
            top_complaints=", ".join(stats["top_complaints"]) or "none identified",
            top_features=", ".join(stats["top_features"]) or "none identified",
            top_feature_mentions=", ".join(stats["top_feature_mentions"]) or "none",
        )

        try:
            result, _, model = await self._client.call(
                system=prompt_cfg["system"],
                user_message=user_message,
                max_tokens=prompt_cfg["max_tokens"],
                temperature=prompt_cfg["temperature"],
            )
        except InsightLLMError as exc:
            logger.warning("segment=%s llm_failed error=%s using_fallback", segment_label, exc)
            result = {
                "description": f"{segment_label} users — LLM description unavailable.",
                "primary_jtbd": "Enjoy Spotify music seamlessly.",
                "primary_pain": "Encountered issues that disrupted their experience.",
                "behavioral_signals": [],
            }
            model = "fallback"

        return UserSegment(
            id=str(uuid.uuid4()),
            segment_label=segment_label,
            description=result.get("description", ""),
            behavioral_signals=result.get("behavioral_signals", [])[:10],
            primary_jtbd=result.get("primary_jtbd", ""),
            primary_pain=result.get("primary_pain", ""),
            review_count=stats["count"],
            fraction_of_total=round(stats["fraction"], 4),
            discovery_friction_rate=round(stats["friction_rate"], 4),
            platform_affinity=stats["dominant_platform"],
            avg_sentiment_score=round(stats["avg_sentiment"], 4),
            top_features_mentioned=stats["top_feature_mentions"][:10],
            generated_at=datetime.now(timezone.utc).isoformat(),
            generation_model=model,
        )


def _compute_stats(reviews: list[dict], total: int) -> dict:
    """Aggregate statistics for a segment group — no LLM needed."""
    count = len(reviews)
    friction_count = sum(1 for r in reviews if r.get("discovery_friction_detected"))
    sentiment_sum = sum(r.get("sentiment_score", 0.0) for r in reviews)
    platform_counter: Counter = Counter()
    complaint_counter: Counter = Counter()
    praise_counter: Counter = Counter()
    feature_counter: Counter = Counter()

    for r in reviews:
        p = r.get("platform") or r.get("dominant_platform", "unknown")
        if p:
            platform_counter[p] += 1
        comp = r.get("primary_complaint")
        if comp:
            complaint_counter[comp] += 1
        praise = r.get("primary_praise")
        if praise:
            praise_counter[praise] += 1
        for feat in r.get("feature_mentions", []):
            if feat:
                feature_counter[feat] += 1

    dominant_platform = platform_counter.most_common(1)[0][0] if platform_counter else "unknown"

    return {
        "count": count,
        "fraction": count / total if total else 0.0,
        "friction_rate": friction_count / count if count else 0.0,
        "avg_sentiment": sentiment_sum / count if count else 0.0,
        "dominant_platform": dominant_platform,
        "top_complaints": _top_n(complaint_counter, 5),
        "top_features": _top_n(praise_counter, 5),
        "top_feature_mentions": _top_n(feature_counter, 10),
    }
