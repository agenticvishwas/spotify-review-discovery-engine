import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from analyzers.response_validator import ResponseValidator

CLEAN_TEXT = (
    "Discover Weekly is broken. It keeps playing the same songs. "
    "I used to love this feature but now I'm thinking of cancelling."
)

VALID_EXTRACTION = {
    "sentiment": "negative",
    "sentiment_score": -0.7,
    "discovery_friction_detected": True,
    "discovery_friction_description": "keeps playing the same songs",
    "primary_complaint": "Discover Weekly repeats songs",
    "primary_praise": None,
    "feature_mentions": ["Discover Weekly"],
    "jtbd_signal": "find fresh music recommendations",
    "user_intent": "enjoy diverse music discovery",
    "root_cause_signal": "recommendation algorithm lacks diversity",
    "user_segment_signal": "power_user",
    "emotion_tags": ["frustration", "disappointment"],
    "listening_behavior_signal": "repetitive",
    "confidence_score": 0.85,
}


class TestResponseValidator:
    def setup_method(self):
        self.validator = ResponseValidator()

    def test_valid_response_passes(self):
        data, result = self.validator.validate(VALID_EXTRACTION.copy(), CLEAN_TEXT)
        assert result.is_valid is True
        assert result.errors == []

    def test_missing_required_field_fails(self):
        raw = VALID_EXTRACTION.copy()
        del raw["sentiment"]
        _, result = self.validator.validate(raw, CLEAN_TEXT)
        assert result.is_valid is False
        assert any("sentiment" in e for e in result.errors)

    def test_missing_confidence_score_uses_proxy(self):
        raw = VALID_EXTRACTION.copy()
        del raw["confidence_score"]
        data, result = self.validator.validate(raw, CLEAN_TEXT)
        assert result.is_valid is True
        assert data["confidence_score"] > 0.0
        assert any("proxy" in w for w in result.warnings)

    def test_proxy_confidence_increases_with_richness(self):
        # All richness fields populated → higher proxy than none populated
        rich = {**VALID_EXTRACTION, "jtbd_signal": "find music", "primary_complaint": "bad recs",
                "user_intent": "explore", "root_cause_signal": "algorithm", "primary_praise": None}
        del rich["confidence_score"]
        sparse = {**VALID_EXTRACTION, "jtbd_signal": None, "primary_complaint": None,
                  "user_intent": None, "root_cause_signal": None, "primary_praise": None}
        del sparse["confidence_score"]

        data_rich, _ = self.validator.validate(rich, CLEAN_TEXT)
        data_sparse, _ = self.validator.validate(sparse, CLEAN_TEXT)
        assert data_rich["confidence_score"] > data_sparse["confidence_score"]

    def test_invalid_sentiment_corrected(self):
        raw = {**VALID_EXTRACTION, "sentiment": "angry"}
        data, result = self.validator.validate(raw, CLEAN_TEXT)
        assert result.is_valid is True
        assert data["sentiment"] == "neutral"
        assert any("sentiment" in w for w in result.warnings)

    def test_sentiment_score_clamped(self):
        raw = {**VALID_EXTRACTION, "sentiment_score": -5.0}
        data, result = self.validator.validate(raw, CLEAN_TEXT)
        assert data["sentiment_score"] == -1.0

    def test_invalid_emotion_tag_removed(self):
        raw = {**VALID_EXTRACTION, "emotion_tags": ["frustration", "rage"]}
        data, result = self.validator.validate(raw, CLEAN_TEXT)
        assert "rage" not in data["emotion_tags"]
        assert "frustration" in data["emotion_tags"]
        assert any("emotion_tag" in w for w in result.warnings)

    def test_hallucination_guard_removes_invented_feature(self):
        # "Radio" is NOT in CLEAN_TEXT
        raw = {**VALID_EXTRACTION, "feature_mentions": ["Discover Weekly", "Radio"]}
        data, result = self.validator.validate(raw, CLEAN_TEXT)
        assert "Radio" not in data["feature_mentions"]
        assert "Discover Weekly" in data["feature_mentions"]
        assert any("hallucination" in w for w in result.warnings)

    def test_hallucination_guard_keeps_present_feature(self):
        raw = {**VALID_EXTRACTION, "feature_mentions": ["Discover Weekly"]}
        data, result = self.validator.validate(raw, CLEAN_TEXT)
        assert "Discover Weekly" in data["feature_mentions"]

    def test_confidence_reduced_after_hallucination(self):
        raw = {**VALID_EXTRACTION, "feature_mentions": ["Daily Mix", "Radio", "Podcast"]}
        data, result = self.validator.validate(raw, CLEAN_TEXT)
        assert result.adjusted_confidence < VALID_EXTRACTION["confidence_score"]

    def test_invalid_segment_falls_back_to_unknown(self):
        raw = {**VALID_EXTRACTION, "user_segment_signal": "expert"}
        data, result = self.validator.validate(raw, CLEAN_TEXT)
        assert data["user_segment_signal"] == "unknown"

    def test_invalid_listening_falls_back_to_unknown(self):
        raw = {**VALID_EXTRACTION, "listening_behavior_signal": "random"}
        data, result = self.validator.validate(raw, CLEAN_TEXT)
        assert data["listening_behavior_signal"] == "unknown"

    def test_non_boolean_friction_coerced(self):
        raw = {**VALID_EXTRACTION, "discovery_friction_detected": 1}
        data, result = self.validator.validate(raw, CLEAN_TEXT)
        assert isinstance(data["discovery_friction_detected"], bool)
        assert data["discovery_friction_detected"] is True
