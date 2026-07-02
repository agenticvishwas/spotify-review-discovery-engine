from typing import Literal, Optional
from pydantic import BaseModel, field_validator

SCHEMA_VERSION = "1.0"

InsightType = Literal["jtbd", "problem", "opportunity", "unmet_need", "segment"]
ConfidenceLevel = Literal["high", "medium", "low"]
TrendDirection = Literal["increasing", "stable", "decreasing"]


def _clamp_unit(v: float, name: str) -> float:
    if not (0.0 <= v <= 1.0):
        raise ValueError(f"{name} must be 0.0–1.0, got {v}")
    return round(v, 4)


class ProductInsight(BaseModel):
    """One PM-facing insight derived from one or more clusters."""

    id: str
    title: str
    description: str
    insight_type: InsightType
    supporting_cluster_ids: list[str]
    supporting_review_ids: list[str]   # 3–10 representative review UUIDs
    supporting_verbatims: list[str]    # direct quote strings (parallel to supporting_review_ids)
    affected_segment: str              # power_user | casual | new | churned | all | unknown
    frequency_score: float             # fraction of total reviews affected [0,1]
    severity_score: float              # avg emotional intensity [0,1]
    uniqueness_score: float            # specificity/novelty of the need [0,1]
    opportunity_score: float           # composite prioritization score [0,1]
    confidence: ConfidenceLevel
    confidence_score: float            # [0,1]
    reasoning: str                     # LLM-generated explanation
    discovery_friction_related: bool
    trend_direction: TrendDirection
    review_required: bool = False      # True if confidence_score < 0.6
    generated_at: str                  # ISO8601
    generation_model: str
    prompt_version: str
    schema_version: str = SCHEMA_VERSION

    @field_validator("frequency_score", "severity_score", "uniqueness_score",
                     "opportunity_score", "confidence_score")
    @classmethod
    def validate_scores(cls, v: float, info) -> float:
        return _clamp_unit(v, info.field_name)

    def to_jsonl(self) -> str:
        return self.model_dump_json()

    model_config = {"frozen": True}


class JTBDProfile(BaseModel):
    """A canonical Jobs-To-Be-Done statement synthesised across one or more clusters."""

    id: str
    job_statement: str          # "When [situation], I want to [motivation], so I can [outcome]"
    short_label: str            # 3–5 word label
    supporting_cluster_ids: list[str]
    user_segments: list[str]    # which segments express this job
    frequency_estimate: int     # estimated number of reviews that reflect this job
    satisfaction_score: float   # how well the current product satisfies this job [0,1]
    gap_score: float            # 1.0 - satisfaction_score
    confidence_score: float     # [0,1]
    gap_description: str
    generated_at: str
    generation_model: str
    prompt_version: str
    schema_version: str = SCHEMA_VERSION

    @field_validator("satisfaction_score", "gap_score", "confidence_score")
    @classmethod
    def validate_scores(cls, v: float, info) -> float:
        return _clamp_unit(v, info.field_name)

    def to_jsonl(self) -> str:
        return self.model_dump_json()

    model_config = {"frozen": True}


class UserSegment(BaseModel):
    """Behavioural characterisation of a distinct user group."""

    id: str
    segment_label: str                  # power_user | casual | new | churned | niche_explorer
    description: str
    behavioral_signals: list[str]
    primary_jtbd: str
    primary_pain: str
    review_count: int
    fraction_of_total: float            # [0,1]
    discovery_friction_rate: float      # [0,1]
    platform_affinity: str
    avg_sentiment_score: float          # [-1,1]
    top_features_mentioned: list[str]
    generated_at: str
    generation_model: str
    schema_version: str = SCHEMA_VERSION

    @field_validator("fraction_of_total", "discovery_friction_rate")
    @classmethod
    def validate_unit(cls, v: float, info) -> float:
        return _clamp_unit(v, info.field_name)

    @field_validator("avg_sentiment_score")
    @classmethod
    def validate_sentiment(cls, v: float) -> float:
        if not (-1.0 <= v <= 1.0):
            raise ValueError(f"avg_sentiment_score must be -1.0–1.0, got {v}")
        return round(v, 4)

    def to_jsonl(self) -> str:
        return self.model_dump_json()

    model_config = {"frozen": True}


class UnmetNeed(BaseModel):
    """A user need not currently addressed by the product."""

    id: str
    need_statement: str                  # "Users need [...] but currently cannot [...]"
    supporting_cluster_ids: list[str]
    affected_segment: str
    expressed_frequency: int             # count of reviews expressing this need
    related_features: list[str]          # existing features that partially address this
    gap_description: str
    confidence_score: float              # [0,1]
    linguistic_patterns_matched: list[str]
    generated_at: str
    generation_model: str
    prompt_version: str
    schema_version: str = SCHEMA_VERSION

    @field_validator("confidence_score")
    @classmethod
    def validate_conf(cls, v: float) -> float:
        return _clamp_unit(v, "confidence_score")

    def to_jsonl(self) -> str:
        return self.model_dump_json()

    model_config = {"frozen": True}
