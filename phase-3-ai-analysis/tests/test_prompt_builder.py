import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "phase-2-preprocessing"))

import pytest
from models.normalized_review import NormalizedReview
from analyzers.prompt_builder import PromptBuilder


def _make_review(**overrides) -> NormalizedReview:
    defaults = dict(
        id="norm-001",
        source_review_id="raw-001",
        clean_text="I love Spotify but Discover Weekly keeps repeating the same songs.",
        normalized_rating=3.0,
        language="en",
        word_count=12,
        sentence_count=1,
        quality_score=0.8,
        is_duplicate=False,
        platform="app_store",
        published_at="2026-06-01T10:00:00+00:00",
        normalized_at="2026-06-01T10:01:00+00:00",
    )
    defaults.update(overrides)
    return NormalizedReview(**defaults)


class TestPromptBuilder:
    def setup_method(self):
        self.builder = PromptBuilder()

    def test_eligible_review_passes(self):
        review = _make_review()
        can, reason = self.builder.can_analyze(review)
        assert can is True
        assert reason == ""

    def test_duplicate_review_rejected(self):
        review = _make_review(is_duplicate=True, duplicate_of_id="norm-000")
        can, reason = self.builder.can_analyze(review)
        assert can is False
        assert "duplicate" in reason

    def test_low_quality_rejected(self):
        review = _make_review(quality_score=0.1)
        can, reason = self.builder.can_analyze(review)
        assert can is False
        assert "quality_score" in reason

    def test_too_few_words_rejected(self):
        review = _make_review(clean_text="ok", word_count=1)
        can, reason = self.builder.can_analyze(review)
        assert can is False
        assert "word_count" in reason

    def test_empty_text_rejected(self):
        review = _make_review(clean_text="   ", word_count=0)
        can, reason = self.builder.can_analyze(review)
        assert can is False

    def test_format_rating_with_value(self):
        assert self.builder.format_rating(4.0) == "4.0/5"

    def test_format_rating_none(self):
        assert self.builder.format_rating(None) == "not provided"

    def test_review_to_context_includes_required_keys(self):
        review = _make_review()
        ctx = self.builder.review_to_context(review)
        assert "platform" in ctx
        assert "normalized_rating" in ctx
        assert "clean_text" in ctx
        assert ctx["platform"] == "app_store"
        assert ctx["clean_text"] == review.clean_text

    def test_review_to_context_null_rating(self):
        review = _make_review(normalized_rating=None)
        ctx = self.builder.review_to_context(review)
        assert ctx["normalized_rating"] == "not provided"
