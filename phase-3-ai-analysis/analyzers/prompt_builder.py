"""Builds and validates LLM prompts from NormalizedReview data."""

import sys
from pathlib import Path
from typing import Optional

_phase2_dir = str(Path(__file__).parent.parent.parent / "phase-2-preprocessing")
if _phase2_dir not in sys.path:
    sys.path.insert(0, _phase2_dir)

from models.normalized_review import NormalizedReview  # noqa: E402


class PromptBuilder:
    """Validates review fields and assembles the user message string for the LLM."""

    MIN_WORD_COUNT = 3

    def can_analyze(self, review: NormalizedReview) -> tuple[bool, str]:
        """Return (True, "") if review should be analyzed, else (False, reason)."""
        if review.is_duplicate:
            return False, "is_duplicate"
        if not review.passes_quality_threshold:
            return False, f"quality_score={review.quality_score:.2f} below threshold"
        if review.word_count < self.MIN_WORD_COUNT:
            return False, f"word_count={review.word_count} too low"
        if not review.clean_text.strip():
            return False, "empty_clean_text"
        return True, ""

    def format_rating(self, normalized_rating: Optional[float]) -> str:
        return f"{normalized_rating}/5" if normalized_rating is not None else "not provided"

    def review_to_context(self, review: NormalizedReview) -> dict:
        """Extract the fields needed to fill the prompt template."""
        return {
            "platform": review.platform,
            "normalized_rating": self.format_rating(review.normalized_rating),
            "clean_text": review.clean_text,
        }
