import logging
from typing import Optional

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.85
NUM_PERM = 128

try:
    from datasketch import MinHash, MinHashLSH
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False
    logger.warning("datasketch not installed — near-duplicate detection will be skipped")


class NearDupDetector:
    """MinHash LSH near-duplicate detection using Jaccard similarity.

    Threshold: 0.85 — reviews >= 85% similar are treated as duplicates.
    Canonical: first registered (earliest in processing order, which reflects
    ingestion order from Phase 1, preserving oldest published_at).
    """

    def __init__(self, threshold: float = SIMILARITY_THRESHOLD):
        self._threshold = threshold
        if _AVAILABLE:
            self._lsh: Optional[MinHashLSH] = MinHashLSH(threshold=threshold, num_perm=NUM_PERM)
        else:
            self._lsh = None

    def is_near_duplicate(self, text: str) -> tuple[bool, Optional[str]]:
        """Return (is_near_dup, canonical_id). canonical_id is None if not a dup."""
        if not _AVAILABLE or self._lsh is None:
            return False, None

        mh = self._build_minhash(text)
        candidates = self._lsh.query(mh)

        if candidates:
            return True, candidates[0]
        return False, None

    def register(self, text: str, review_id: str) -> None:
        """Register a review as canonical in the LSH index."""
        if not _AVAILABLE or self._lsh is None:
            return
        mh = self._build_minhash(text)
        try:
            self._lsh.insert(review_id, mh)
        except ValueError:
            pass  # already registered — idempotent

    def _build_minhash(self, text: str) -> "MinHash":
        mh = MinHash(num_perm=NUM_PERM)
        for token in set(text.lower().split()):
            mh.update(token.encode("utf-8"))
        return mh
