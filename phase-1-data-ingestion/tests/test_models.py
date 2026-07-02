"""Unit tests for RawReview and IngestionBatch models."""

import json
import pytest
from pydantic import ValidationError

from models.raw_review import RawReview, make_stable_id, VALID_PLATFORMS
from models.ingestion_batch import IngestionBatch, PlatformStats

BATCH_ID = "test-batch-001"


# ── make_stable_id ───────────────────────────────────────────────────────────

class TestMakeStableId:
    def test_deterministic(self):
        id1 = make_stable_id("app_store", "user1", "2024-01-01", "Great app")
        id2 = make_stable_id("app_store", "user1", "2024-01-01", "Great app")
        assert id1 == id2

    def test_different_platforms_produce_different_ids(self):
        id1 = make_stable_id("app_store", "user1", "2024-01-01", "text")
        id2 = make_stable_id("google_play", "user1", "2024-01-01", "text")
        assert id1 != id2

    def test_different_authors_produce_different_ids(self):
        id1 = make_stable_id("reddit", "user1", "2024-01-01", "text")
        id2 = make_stable_id("reddit", "user2", "2024-01-01", "text")
        assert id1 != id2

    def test_none_author_handled(self):
        result = make_stable_id("community", None, "2024-01-01", "some text")
        assert isinstance(result, str)
        assert len(result) == 36  # UUID string length

    def test_uses_first_50_chars_only(self):
        text_a = "A" * 50 + "different suffix"
        text_b = "A" * 50 + "another suffix"
        # Same first 50 chars → same ID
        assert make_stable_id("app_store", "u", "2024-01-01", text_a) == \
               make_stable_id("app_store", "u", "2024-01-01", text_b)

    def test_output_is_valid_uuid_format(self):
        import uuid
        result = make_stable_id("reddit", "u", "2024-01-01", "text")
        # Should not raise
        uuid.UUID(result)


# ── RawReview validation ─────────────────────────────────────────────────────

class TestRawReviewValidation:
    def _valid_review(self, **overrides) -> dict:
        base = {
            "id": make_stable_id("app_store", "user1", "2024-01-15", "Great music"),
            "source_platform": "app_store",
            "raw_text": "Great music discovery feature!",
            "published_at": "2024-01-15T10:00:00+00:00",
            "source_url": "https://apps.apple.com/review/123",
            "ingested_at": "2024-01-15T12:00:00+00:00",
            "ingestion_batch_id": BATCH_ID,
            "rating": 5,
            "author_id": "user1",
        }
        base.update(overrides)
        return base

    def test_valid_review_creates_successfully(self):
        review = RawReview(**self._valid_review())
        assert review.source_platform == "app_store"
        assert review.rating == 5

    def test_all_valid_platforms_accepted(self):
        for platform in VALID_PLATFORMS:
            review = RawReview(**self._valid_review(source_platform=platform))
            assert review.source_platform == platform

    def test_invalid_platform_raises(self):
        with pytest.raises(ValidationError, match="source_platform"):
            RawReview(**self._valid_review(source_platform="tiktok"))

    def test_empty_text_raises(self):
        with pytest.raises(ValidationError):
            RawReview(**self._valid_review(raw_text=""))

    def test_whitespace_only_text_raises(self):
        with pytest.raises(ValidationError):
            RawReview(**self._valid_review(raw_text="   "))

    def test_rating_none_is_valid(self):
        review = RawReview(**self._valid_review(rating=None))
        assert review.rating is None

    def test_rating_1_to_5_valid(self):
        for r in range(1, 6):
            review = RawReview(**self._valid_review(rating=r))
            assert review.rating == r

    def test_rating_0_raises(self):
        with pytest.raises(ValidationError):
            RawReview(**self._valid_review(rating=0))

    def test_rating_6_raises(self):
        with pytest.raises(ValidationError):
            RawReview(**self._valid_review(rating=6))

    def test_author_id_none_is_valid(self):
        review = RawReview(**self._valid_review(author_id=None))
        assert review.author_id is None

    def test_schema_version_defaults_to_1_0(self):
        review = RawReview(**self._valid_review())
        assert review.schema_version == "1.0"

    def test_to_jsonl_is_valid_json(self):
        review = RawReview(**self._valid_review())
        line = review.to_jsonl()
        parsed = json.loads(line)
        assert parsed["source_platform"] == "app_store"
        assert parsed["schema_version"] == "1.0"

    def test_validation_errors_returns_list(self):
        review = RawReview(**self._valid_review())
        assert review.validation_errors() == []

    def test_to_jsonl_is_single_line(self):
        review = RawReview(**self._valid_review())
        assert "\n" not in review.to_jsonl()

    def test_review_is_immutable(self):
        review = RawReview(**self._valid_review())
        with pytest.raises(Exception):
            review.rating = 3  # type: ignore[misc]


# ── IngestionBatch ───────────────────────────────────────────────────────────

class TestIngestionBatch:
    def test_default_status_is_running(self):
        batch = IngestionBatch(
            batch_id=BATCH_ID,
            platform="app_store",
            started_at="2024-01-15T12:00:00+00:00",
        )
        assert batch.status == "running"

    def test_platform_stats_record_rejection(self):
        stats = PlatformStats()
        stats.record_rejection("empty_text")
        stats.record_rejection("empty_text")
        stats.record_rejection("missing_date")
        assert stats.rejected == 3
        assert stats.rejection_reasons["empty_text"] == 2
        assert stats.rejection_reasons["missing_date"] == 1

    def test_batch_model_dump_is_serializable(self):
        batch = IngestionBatch(
            batch_id=BATCH_ID,
            platform="google_play",
            started_at="2024-01-15T12:00:00+00:00",
        )
        data = batch.model_dump()
        json.dumps(data)  # must not raise
