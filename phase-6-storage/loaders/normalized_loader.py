from __future__ import annotations
import json
import logging
from .base_loader import BaseLoader

logger = logging.getLogger(__name__)


class NormalizedLoader(BaseLoader):
    def load_all(self) -> tuple[list[dict], int]:
        records: list[dict] = []
        skipped = 0
        for raw in self._iter_jsonl():
            if not raw.get("id") or not raw.get("source_review_id"):
                skipped += 1
                continue
            filters = raw.get("filters_applied", [])
            records.append({
                "id": raw["id"],
                "source_review_id": raw["source_review_id"],
                "clean_text": raw.get("clean_text", ""),
                "normalized_rating": raw.get("normalized_rating"),
                "language": raw.get("language", "unknown"),
                "word_count": raw.get("word_count", 0),
                "sentence_count": raw.get("sentence_count"),
                "quality_score": raw.get("quality_score", 0.0),
                "is_duplicate": int(bool(raw.get("is_duplicate", False))),
                "duplicate_of_id": raw.get("duplicate_of_id"),
                "platform": raw.get("platform", "unknown"),
                "published_at": raw.get("published_at"),
                "normalized_at": raw.get("normalized_at", ""),
                "filters_applied": json.dumps(filters) if isinstance(filters, list) else filters,
                "schema_version": raw.get("schema_version", "1.0"),
            })
        logger.info("NormalizedReview loader: %d loaded, %d skipped", len(records), skipped)
        return records, skipped
