import hashlib
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ExactDeduplicator:
    """SHA-256 based exact deduplication with optional persistent cross-batch index.

    Hash key: SHA-256 of clean_text.strip().lower()
    Canonical record: first registered (pipeline processes records in ingestion order).
    """

    def __init__(self, index_path: Optional[Path] = None):
        self._index_path = index_path
        self._seen: dict[str, str] = {}  # hash → canonical review_id
        if index_path and index_path.exists():
            self._load_index()

    def is_duplicate(self, text: str) -> tuple[bool, Optional[str]]:
        """Return (is_duplicate, canonical_id). canonical_id is None if not a duplicate."""
        h = self._hash(text)
        if h in self._seen:
            return True, self._seen[h]
        return False, None

    def register(self, text: str, review_id: str) -> None:
        """Register a review as canonical for its hash. No-op if hash already known."""
        h = self._hash(text)
        if h not in self._seen:
            self._seen[h] = review_id

    def save_index(self) -> None:
        """Persist the hash index to disk for cross-batch deduplication."""
        if not self._index_path:
            return
        self._index_path.parent.mkdir(parents=True, exist_ok=True)
        self._index_path.write_text(
            json.dumps(self._seen, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.info("phase=2 action=save_exact_index records=%d path=%s", len(self._seen), self._index_path)

    def _load_index(self) -> None:
        try:
            self._seen = json.loads(self._index_path.read_text(encoding="utf-8"))
            logger.info("phase=2 action=load_exact_index records=%d path=%s", len(self._seen), self._index_path)
        except Exception as exc:
            logger.warning("Failed to load exact dedup index from %s: %s", self._index_path, exc)

    @staticmethod
    def _hash(text: str) -> str:
        return hashlib.sha256(text.strip().lower().encode("utf-8")).hexdigest()
