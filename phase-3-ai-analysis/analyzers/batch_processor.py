"""Async batch processor: concurrency control, progress tracking, resume capability."""

import asyncio
import logging
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Optional

from schemas.analyzed_review import AnalyzedReview
from analyzers.llm_client import LLMClient, LLMExtractionError
from analyzers.prompt_builder import PromptBuilder
from analyzers.response_validator import ResponseValidator

logger = logging.getLogger(__name__)

DEFAULT_CONCURRENCY = 5
LOW_CONFIDENCE_THRESHOLD = 0.5


class BatchStats:
    def __init__(self):
        self.total = 0
        self.success = 0
        self.failed = 0
        self.skipped = 0
        self.low_confidence = 0
        self.total_tokens = 0

    def as_dict(self) -> dict:
        return {
            "total_submitted": self.total,
            "success": self.success,
            "failed": self.failed,
            "skipped": self.skipped,
            "low_confidence": self.low_confidence,
            "total_tokens_used": self.total_tokens,
            "failure_rate": round(self.failed / self.total, 4) if self.total else 0.0,
        }


class BatchProcessor:
    """Processes a list of NormalizedReview objects through the LLM pipeline.

    Calls on_result(AnalyzedReview) for each completed analysis so the caller
    can write results incrementally (enabling resume on next run).
    """

    def __init__(
        self,
        llm_client: LLMClient,
        concurrency: int = DEFAULT_CONCURRENCY,
    ):
        self._client = llm_client
        self._concurrency = concurrency
        self._analysis_model = llm_client.model
        self._prompt_version = llm_client.prompt_version
        self._builder = PromptBuilder()
        self._validator = ResponseValidator()

    async def process(
        self,
        reviews: list,
        on_result: Callable[[AnalyzedReview], None],
        already_analyzed_ids: Optional[set[str]] = None,
    ) -> BatchStats:
        """Analyze all eligible reviews and call on_result for each output.

        Args:
            reviews: list of NormalizedReview objects from Phase 2.
            on_result: callback invoked with each completed AnalyzedReview.
            already_analyzed_ids: normalized_review_id values already processed (resume set).
        """
        analyzed_ids = already_analyzed_ids or set()
        stats = BatchStats()
        semaphore = asyncio.Semaphore(self._concurrency)
        lock = asyncio.Lock()

        eligible = []
        for review in reviews:
            can, reason = self._builder.can_analyze(review)
            if not can:
                logger.debug("skip review=%s reason=%s", review.id, reason)
                stats.skipped += 1
                continue
            if review.id in analyzed_ids:
                logger.debug("skip review=%s reason=already_analyzed", review.id)
                stats.skipped += 1
                continue
            eligible.append(review)

        stats.total = len(eligible)
        logger.info(
            "phase=3 event=batch_start eligible=%d skipped=%d concurrency=%d",
            stats.total, stats.skipped, self._concurrency,
        )

        async def process_one(review, index: int) -> None:
            async with semaphore:
                result = await self._analyze_with_retry(review)
                async with lock:
                    stats.total_tokens += result.analysis_tokens_used
                    if result.analysis_status == "success":
                        stats.success += 1
                    elif result.analysis_status == "failed":
                        stats.failed += 1
                    if result.confidence_score < LOW_CONFIDENCE_THRESHOLD:
                        stats.low_confidence += 1
                    on_result(result)
                    if (index + 1) % 50 == 0:
                        logger.info(
                            "phase=3 event=progress processed=%d/%d",
                            index + 1, stats.total,
                        )

        await asyncio.gather(
            *[process_one(r, i) for i, r in enumerate(eligible)],
            return_exceptions=False,
        )

        logger.info(
            "phase=3 event=batch_complete %s",
            " ".join(f"{k}={v}" for k, v in stats.as_dict().items()),
        )
        return stats

    async def _analyze_with_retry(self, review) -> AnalyzedReview:
        """Attempt LLM extraction up to 3 times, returning a failed record on exhaustion."""
        max_attempts = 3
        last_error: Optional[Exception] = None

        for attempt in range(1, max_attempts + 1):
            try:
                raw, tokens = await self._client.extract(
                    clean_text=review.clean_text,
                    platform=review.platform,
                    normalized_rating=review.normalized_rating,
                )
                validated, result = self._validator.validate(raw, review.clean_text)

                if not result.is_valid:
                    logger.warning(
                        "phase=3 review=%s attempt=%d validation_errors=%s",
                        review.id, attempt, result.errors,
                    )
                    last_error = ValueError(f"validation errors: {result.errors}")
                    continue

                if result.warnings:
                    logger.debug(
                        "phase=3 review=%s warnings=%s", review.id, result.warnings
                    )

                status = "low_confidence" if result.adjusted_confidence < LOW_CONFIDENCE_THRESHOLD else "success"

                return AnalyzedReview(
                    id=str(uuid.uuid4()),
                    normalized_review_id=review.id,
                    source_review_id=review.source_review_id,
                    sentiment=validated["sentiment"],
                    sentiment_score=validated["sentiment_score"],
                    discovery_friction_detected=validated["discovery_friction_detected"],
                    discovery_friction_description=validated.get("discovery_friction_description"),
                    primary_complaint=validated.get("primary_complaint"),
                    primary_praise=validated.get("primary_praise"),
                    feature_mentions=validated.get("feature_mentions", []),
                    jtbd_signal=validated.get("jtbd_signal"),
                    user_intent=validated.get("user_intent"),
                    root_cause_signal=validated.get("root_cause_signal"),
                    user_segment_signal=validated.get("user_segment_signal", "unknown"),
                    emotion_tags=validated.get("emotion_tags", []),
                    listening_behavior_signal=validated.get("listening_behavior_signal", "unknown"),
                    confidence_score=result.adjusted_confidence,
                    analysis_model=self._analysis_model,
                    analysis_tokens_used=tokens,
                    analyzed_at=datetime.now(timezone.utc).isoformat(),
                    analysis_status=status,
                    prompt_version=self._prompt_version,
                )

            except LLMExtractionError as exc:
                logger.warning(
                    "phase=3 review=%s attempt=%d llm_error=%s", review.id, attempt, exc
                )
                last_error = exc
            except Exception as exc:
                logger.error(
                    "phase=3 review=%s attempt=%d unexpected_error=%s", review.id, attempt, exc
                )
                last_error = exc

        logger.error(
            "phase=3 review=%s all_attempts_failed skip_reason=llm_failure error=%s",
            review.id, last_error,
        )
        return self._failed_record(review)

    def _failed_record(self, review) -> AnalyzedReview:
        return AnalyzedReview(
            id=str(uuid.uuid4()),
            normalized_review_id=review.id,
            source_review_id=review.source_review_id,
            sentiment="neutral",
            sentiment_score=0.0,
            discovery_friction_detected=False,
            confidence_score=0.0,
            analysis_model=self._analysis_model,
            analysis_tokens_used=0,
            analyzed_at=datetime.now(timezone.utc).isoformat(),
            analysis_status="failed",
            prompt_version=self._prompt_version,
        )
