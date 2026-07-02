from typing import Literal, Optional
from pydantic import BaseModel, field_validator

SCHEMA_VERSION = "1.0"
PROMPT_VERSION = "1.3"
ANALYSIS_MODEL = "claude-sonnet-4-6"

SentimentType = Literal["positive", "negative", "neutral", "mixed"]
SegmentType = Literal["power_user", "casual", "new", "churned", "unknown"]
ListeningBehaviorType = Literal["repetitive", "exploratory", "mood-based", "activity-based", "unknown"]
EmotionTag = Literal["frustration", "delight", "confusion", "boredom", "hope", "disappointment"]
AnalysisStatus = Literal["success", "failed", "low_confidence"]


class AnalyzedReview(BaseModel):
    id: str
    normalized_review_id: str
    source_review_id: str
    sentiment: SentimentType
    sentiment_score: float
    discovery_friction_detected: bool
    discovery_friction_description: Optional[str] = None
    primary_complaint: Optional[str] = None
    primary_praise: Optional[str] = None
    feature_mentions: list[str] = []
    jtbd_signal: Optional[str] = None
    user_intent: Optional[str] = None
    root_cause_signal: Optional[str] = None
    user_segment_signal: SegmentType = "unknown"
    emotion_tags: list[str] = []
    listening_behavior_signal: ListeningBehaviorType = "unknown"
    confidence_score: float
    analysis_model: str = ANALYSIS_MODEL
    prompt_version: str = PROMPT_VERSION
    analyzed_at: str
    schema_version: str = SCHEMA_VERSION
    analysis_tokens_used: int = 0
    analysis_status: AnalysisStatus = "success"

    @field_validator("sentiment_score")
    @classmethod
    def validate_sentiment_score(cls, v: float) -> float:
        if not (-1.0 <= v <= 1.0):
            raise ValueError(f"sentiment_score must be -1.0–1.0, got {v}")
        return round(v, 4)

    @field_validator("confidence_score")
    @classmethod
    def validate_confidence_score(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError(f"confidence_score must be 0.0–1.0, got {v}")
        return round(v, 4)

    def to_jsonl(self) -> str:
        return self.model_dump_json()

    model_config = {"frozen": True}
