from __future__ import annotations
import json
import logging
from .base_loader import BaseLoader

logger = logging.getLogger(__name__)


class AnalyzedLoader(BaseLoader):
    def load_all(self) -> tuple[list[dict], int]:
        records: list[dict] = []
        skipped = 0
        for raw in self._iter_jsonl():
            if not raw.get("id") or not raw.get("normalized_review_id"):
                skipped += 1
                continue
            # Include all statuses; Phase 7 filters by status/confidence
            records.append({
                "id": raw["id"],
                "normalized_review_id": raw["normalized_review_id"],
                "source_review_id": raw.get("source_review_id", ""),
                "sentiment": raw.get("sentiment", "unknown"),
                "sentiment_score": raw.get("sentiment_score", 0.0),
                "discovery_friction_detected": int(bool(raw.get("discovery_friction_detected", False))),
                "discovery_friction_description": raw.get("discovery_friction_description"),
                "primary_complaint": raw.get("primary_complaint"),
                "primary_praise": raw.get("primary_praise"),
                "feature_mentions": json.dumps(raw.get("feature_mentions", [])),
                "jtbd_signal": raw.get("jtbd_signal"),
                "user_intent": raw.get("user_intent"),
                "root_cause_signal": raw.get("root_cause_signal"),
                "user_segment_signal": raw.get("user_segment_signal", "unknown"),
                "emotion_tags": json.dumps(raw.get("emotion_tags", [])),
                "listening_behavior_signal": raw.get("listening_behavior_signal"),
                "confidence_score": raw.get("confidence_score", 0.0),
                "analysis_model": raw.get("analysis_model", ""),
                "prompt_version": raw.get("prompt_version", ""),
                "analyzed_at": raw.get("analyzed_at", ""),
                "analysis_tokens_used": raw.get("analysis_tokens_used", 0),
                "analysis_status": raw.get("analysis_status", "success"),
                "schema_version": raw.get("schema_version", "1.0"),
            })
        logger.info("AnalyzedReview loader: %d loaded, %d skipped", len(records), skipped)
        return records, skipped
