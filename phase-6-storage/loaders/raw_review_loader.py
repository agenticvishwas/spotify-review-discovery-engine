from __future__ import annotations
import logging
from .base_loader import BaseLoader

logger = logging.getLogger(__name__)


class RawReviewLoader(BaseLoader):
    def load_all(self) -> tuple[list[dict], int]:
        records: list[dict] = []
        skipped = 0
        for raw in self._iter_jsonl():
            if not raw.get("id") or not raw.get("raw_text"):
                skipped += 1
                continue
            records.append({
                "id": raw["id"],
                "source_platform": raw.get("source_platform", "unknown"),
                "raw_text": raw["raw_text"],
                "rating": raw.get("rating"),
                "author_id": raw.get("author_id"),
                "published_at": raw.get("published_at", ""),
                "source_url": raw.get("source_url", ""),
                "ingested_at": raw.get("ingested_at", ""),
                "ingestion_batch_id": raw.get("ingestion_batch_id", ""),
                "schema_version": raw.get("schema_version", "1.0"),
            })
        logger.info("RawReview loader: %d loaded, %d skipped", len(records), skipped)
        return records, skipped
