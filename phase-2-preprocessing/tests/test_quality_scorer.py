import pytest
from validators.quality_scorer import QualityScorer


class TestQualityScorer:
    def setup_method(self):
        self.scorer = QualityScorer()

    def test_empty_text_scores_zero(self):
        assert self.scorer.score("") == 0.0

    def test_single_word_scores_zero(self):
        assert self.scorer.score("Great") == 0.0

    def test_short_text_under_10_words_no_word_count_bonus(self):
        text = "I love Spotify."
        score = self.scorer.score(text)
        # word count < 10, so no +0.3, but may get not-generic-template +0.1
        assert score <= 0.1

    def test_ten_plus_words_gets_base_bonus(self):
        text = "I really enjoy using Spotify every single day for my music."
        score = self.scorer.score(text)
        assert score >= 0.3

    def test_thirty_plus_words_gets_extra_bonus(self):
        text = (
            "I really enjoy using Spotify every single day for my music. "
            "The discover weekly is fantastic and I always find new songs that I love. "
            "The app has great features."
        )
        score = self.scorer.score(text)
        assert score >= 0.5

    def test_two_sentences_gets_sentence_bonus(self):
        text = "I love Spotify. The shuffle feature is great and I use it every day for work."
        score = self.scorer.score(text)
        # Should get word count bonus + sentence bonus
        assert score >= 0.3

    def test_specific_content_mention_adds_bonus(self):
        text = (
            "The app crashed after the latest update and the shuffle feature is broken. "
            "I reported this bug to support but no fix yet."
        )
        score = self.scorer.score(text)
        assert score >= 0.5

    def test_generic_template_reduces_score(self):
        score_generic = self.scorer.score("great app")
        score_specific = self.scorer.score(
            "I really enjoy using Spotify because the playlists are well curated."
        )
        assert score_specific > score_generic

    def test_score_bounded_zero_to_one(self):
        texts = [
            "",
            "ok",
            "great app",
            "This is a moderately detailed review of Spotify.",
            "I have been using Spotify for years. The discover weekly playlist is excellent "
            "and the podcast feature works really well. The app crashed once but was quickly "
            "fixed in the next update. Highly recommend for anyone who loves music.",
        ]
        for text in texts:
            score = self.scorer.score(text)
            assert 0.0 <= score <= 1.0, f"Score out of range for: {text!r}"

    def test_word_count_accuracy(self):
        assert self.scorer.word_count("one two three") == 3
        assert self.scorer.word_count("") == 0
        assert self.scorer.word_count("  spaces   between  words  ") == 3

    def test_sentence_count_accuracy(self):
        assert self.scorer.sentence_count("One sentence.") == 1
        assert self.scorer.sentence_count("First! Second? Third.") == 3
        assert self.scorer.sentence_count("") == 0

    def test_score_is_deterministic(self):
        text = "Spotify is great but the shuffle feature needs improvement."
        score1 = self.scorer.score(text)
        score2 = self.scorer.score(text)
        assert score1 == score2

    def test_full_scoring_breakdown(self):
        # This text should max out all conditions:
        # word_count >= 10 (+0.3), >= 30 (+0.2), sentence >= 2 (+0.2),
        # specific content (+0.2), not generic (+0.1)
        text = (
            "The app crashed after the latest update and the playlist shuffle is completely broken. "
            "I reported this bug to support but there has been no fix after two weeks. "
            "The discover weekly feature used to work perfectly but now it's slow and unreliable."
        )
        score = self.scorer.score(text)
        assert score == 1.0


class TestNormalizedReviewIntegration:
    """Integration: verify NormalizedReview model accepts quality scorer output."""

    def test_normalized_review_with_scored_text(self):
        from models.normalized_review import NormalizedReview
        import uuid
        from datetime import datetime, timezone

        scorer = QualityScorer()
        text = "Spotify crashed after the latest update. The playlist feature is broken and slow."
        score = scorer.score(text)

        review = NormalizedReview(
            id=str(uuid.uuid4()),
            source_review_id=str(uuid.uuid4()),
            clean_text=text,
            normalized_rating=4.0,
            language="en",
            word_count=scorer.word_count(text),
            sentence_count=scorer.sentence_count(text),
            quality_score=score,
            is_duplicate=False,
            platform="app_store",
            published_at="2024-01-15T10:00:00+00:00",
            normalized_at=datetime.now(timezone.utc).isoformat(),
        )
        assert review.passes_quality_threshold
        assert review.quality_score == score
