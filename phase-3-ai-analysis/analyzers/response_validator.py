"""JSON schema validation and hallucination guard for LLM extraction outputs."""

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

VALID_SENTIMENTS = {"positive", "negative", "neutral", "mixed"}
VALID_SEGMENTS = {"power_user", "casual", "new", "churned", "unknown"}
VALID_LISTENING = {"repetitive", "exploratory", "mood-based", "activity-based", "unknown"}
VALID_EMOTIONS = {"frustration", "delight", "confusion", "boredom", "hope", "disappointment"}

# Only truly structural fields are required — small models (Ollama/qwen) reliably
# produce sentiment and friction signals but often omit confidence_score since
# self-assessment is a meta-task they skip. We compute it as a proxy instead.
REQUIRED_FIELDS = {"sentiment", "sentiment_score", "discovery_friction_detected"}

# Fields whose presence signals a richer, more confident extraction
_RICHNESS_FIELDS = ("jtbd_signal", "primary_complaint", "primary_praise",
                    "user_intent", "root_cause_signal")

# Baseline confidence when the model omits confidence_score (required fields present)
_BASE_PROXY_CONFIDENCE = 0.70
# Bonus per richness field populated (max contribution: len * bonus)
_RICHNESS_BONUS = 0.03
# Penalty applied to confidence_score when a hallucination is detected
_HALLUCINATION_PENALTY = 0.2
# Penalty per validation warning that weakens overall reliability
_MISSING_FIELD_PENALTY = 0.05


class ValidationResult:
    __slots__ = ("is_valid", "errors", "warnings", "adjusted_confidence")

    def __init__(
        self,
        is_valid: bool,
        errors: list[str],
        warnings: list[str],
        adjusted_confidence: float,
    ):
        self.is_valid = is_valid
        self.errors = errors
        self.warnings = warnings
        self.adjusted_confidence = adjusted_confidence


class ResponseValidator:
    """Validates and sanitizes the dict returned from the LLM tool_use call.

    Responsibilities:
    - Reject responses missing required fields (is_valid=False).
    - Clamp numeric fields to their valid ranges.
    - Enforce enum membership; fall back to "unknown" for bad values.
    - Hallucination guard: remove feature_mentions not found in source text.
    - Adjust confidence_score downward for detected issues.
    """

    def validate(
        self, raw: dict[str, Any], clean_text: str
    ) -> tuple[dict[str, Any], ValidationResult]:
        errors: list[str] = []
        warnings: list[str] = []
        data = dict(raw)

        # --- Required fields ---
        for field in REQUIRED_FIELDS:
            if field not in data:
                errors.append(f"missing required field: {field}")

        if errors:
            return data, ValidationResult(False, errors, warnings, 0.0)

        # --- sentiment ---
        if data["sentiment"] not in VALID_SENTIMENTS:
            warnings.append(f"invalid sentiment '{data['sentiment']}' → 'neutral'")
            data["sentiment"] = "neutral"

        # --- sentiment_score ---
        data["sentiment_score"] = float(
            max(-1.0, min(1.0, data.get("sentiment_score", 0.0)))
        )

        # --- discovery_friction_detected ---
        if not isinstance(data["discovery_friction_detected"], bool):
            data["discovery_friction_detected"] = bool(data["discovery_friction_detected"])

        # --- user_segment_signal ---
        seg = data.get("user_segment_signal", "unknown")
        if seg not in VALID_SEGMENTS:
            warnings.append(f"invalid user_segment_signal '{seg}' → 'unknown'")
            data["user_segment_signal"] = "unknown"

        # --- listening_behavior_signal ---
        lb = data.get("listening_behavior_signal", "unknown")
        if lb not in VALID_LISTENING:
            warnings.append(f"invalid listening_behavior_signal '{lb}' → 'unknown'")
            data["listening_behavior_signal"] = "unknown"

        # --- emotion_tags ---
        raw_tags = data.get("emotion_tags", [])
        if not isinstance(raw_tags, list):
            raw_tags = []
        valid_tags = [t for t in raw_tags if t in VALID_EMOTIONS]
        invalid = set(raw_tags) - set(valid_tags)
        if invalid:
            warnings.append(f"removed invalid emotion_tags: {invalid}")
        data["emotion_tags"] = valid_tags

        # --- feature_mentions — hallucination guard ---
        raw_mentions = data.get("feature_mentions", [])
        if not isinstance(raw_mentions, list):
            raw_mentions = []
        verified, removed = self._guard_feature_mentions(raw_mentions, clean_text)
        if removed:
            warnings.append(
                f"hallucination guard removed {len(removed)} feature_mention(s): {removed}"
            )
        data["feature_mentions"] = verified

        # --- confidence_score ---
        if "confidence_score" in data:
            # Model provided self-assessed confidence — clamp and apply penalties
            base_conf = float(max(0.0, min(1.0, data["confidence_score"])))
        else:
            # Model omitted confidence (common with small local models) — compute proxy
            # from field completeness: more optional fields filled → higher confidence
            richness = sum(1 for f in _RICHNESS_FIELDS if data.get(f))
            base_conf = min(1.0, _BASE_PROXY_CONFIDENCE + richness * _RICHNESS_BONUS)
            warnings.append(f"confidence_score missing — proxy computed from field richness ({richness}/{len(_RICHNESS_FIELDS)} fields)")

        penalty = len(removed) * _HALLUCINATION_PENALTY + len(warnings) * _MISSING_FIELD_PENALTY
        adjusted = round(max(0.0, base_conf - penalty), 4)
        data["confidence_score"] = adjusted

        return data, ValidationResult(True, errors, warnings, adjusted)

    def _guard_feature_mentions(
        self, mentions: list[str], clean_text: str
    ) -> tuple[list[str], list[str]]:
        """Remove mentions whose key terms do not appear in clean_text."""
        text_lower = clean_text.lower()
        verified: list[str] = []
        removed: list[str] = []

        for mention in mentions:
            if self._mention_in_text(mention, text_lower):
                verified.append(mention)
            else:
                removed.append(mention)

        return verified, removed

    def _mention_in_text(self, mention: str, text_lower: str) -> bool:
        words = re.findall(r"[a-z]+", mention.lower())
        stopwords = {"the", "a", "an", "for", "and", "or", "of", "in", "to", "with"}
        significant = [w for w in words if w not in stopwords and len(w) > 2]
        if not significant:
            return True
        return any(w in text_lower for w in significant)
