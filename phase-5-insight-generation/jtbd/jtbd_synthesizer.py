"""Cross-cluster JTBD synthesis.

Merges JTBDProfiles with similar job statements into canonical profiles.
Similarity is measured by keyword overlap (no embedding cost, no API call).
Profiles with overlap > threshold are merged; the one with the highest
frequency_estimate becomes the canonical representative.

This is a deterministic operation — no LLM call required.
"""

import logging
import re
import uuid
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timezone

from schemas.product_insight import JTBDProfile

logger = logging.getLogger(__name__)

_DEFAULT_SIMILARITY_THRESHOLD = 0.40
_STOPWORDS = frozenset(
    "when i want to so can the a an and or but for of in on at with my using "
    "listen music song play album artist track discover find".split()
)


def _keyword_set(text: str) -> set[str]:
    words = re.findall(r"[a-z]+", text.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 3}


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    return len(a & b) / len(union)


class JTBDSynthesizer:
    """Merges near-duplicate JTBD profiles across clusters into canonical forms.

    Algorithm:
        1. Convert each job_statement to a keyword set.
        2. Build a union-find (disjoint set) structure to group similar profiles.
        3. For each group, pick the highest-frequency profile as canonical.
        4. Merge supporting_cluster_ids and sum frequency_estimates.
        5. Recompute gap_score from the merged satisfaction_score average.
    """

    def __init__(self, similarity_threshold: float = _DEFAULT_SIMILARITY_THRESHOLD):
        self._threshold = similarity_threshold

    def merge(self, profiles: list[JTBDProfile]) -> list[JTBDProfile]:
        if not profiles:
            return []

        keyword_sets = [_keyword_set(p.job_statement) for p in profiles]
        parent = list(range(len(profiles)))

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(x: int, y: int) -> None:
            parent[find(x)] = find(y)

        for i in range(len(profiles)):
            for j in range(i + 1, len(profiles)):
                sim = _jaccard(keyword_sets[i], keyword_sets[j])
                if sim >= self._threshold:
                    union(i, j)

        groups: dict[int, list[int]] = defaultdict(list)
        for i in range(len(profiles)):
            groups[find(i)].append(i)

        merged: list[JTBDProfile] = []
        now = datetime.now(timezone.utc).isoformat()

        for root, members in groups.items():
            if len(members) == 1:
                merged.append(profiles[members[0]])
                continue

            # Pick canonical = highest frequency_estimate
            canonical_idx = max(members, key=lambda i: profiles[i].frequency_estimate)
            canonical = profiles[canonical_idx]

            all_cluster_ids: list[str] = []
            all_segments: set[str] = set()
            total_freq = 0
            sat_sum = 0.0

            for idx in members:
                p = profiles[idx]
                all_cluster_ids.extend(p.supporting_cluster_ids)
                all_segments.update(p.user_segments)
                total_freq += p.frequency_estimate
                sat_sum += p.satisfaction_score

            avg_sat = round(sat_sum / len(members), 4)
            avg_sat = max(0.0, min(1.0, avg_sat))

            merged.append(
                JTBDProfile(
                    id=str(uuid.uuid4()),
                    job_statement=canonical.job_statement,
                    short_label=canonical.short_label,
                    supporting_cluster_ids=list(dict.fromkeys(all_cluster_ids)),
                    user_segments=sorted(all_segments),
                    frequency_estimate=total_freq,
                    satisfaction_score=avg_sat,
                    gap_score=round(1.0 - avg_sat, 4),
                    confidence_score=round(
                        sum(profiles[i].confidence_score for i in members) / len(members), 4
                    ),
                    gap_description=canonical.gap_description,
                    generated_at=now,
                    generation_model=canonical.generation_model,
                    prompt_version=canonical.prompt_version,
                )
            )
            logger.debug(
                "jtbd=merged group_size=%d canonical_label=%s total_freq=%d",
                len(members), canonical.short_label, total_freq,
            )

        merged.sort(key=lambda p: p.frequency_estimate, reverse=True)
        logger.info("jtbd=synthesis_complete input=%d output=%d", len(profiles), len(merged))
        return merged
