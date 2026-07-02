from typing import Literal, Optional
from pydantic import BaseModel, field_validator

SCHEMA_VERSION = "1.0"
LABELING_PROMPT_VERSION = "1.0"
CLUSTERING_ALGORITHM = "hdbscan"

TrendDirection = Literal["increasing", "stable", "decreasing"]
MIN_CLUSTER_SIZE_FOR_INSIGHT = 5


class ReviewCluster(BaseModel):
    id: str
    label: str
    theme: str
    is_discovery_related: bool
    member_review_ids: list[str]
    representative_review_ids: list[str]
    centroid_embedding: list[float]
    size: int
    avg_sentiment_score: float
    discovery_friction_rate: float
    dominant_platform: str
    platform_distribution: dict[str, float]
    dominant_emotion: str
    top_features_mentioned: list[str]
    trend_direction: TrendDirection
    trend_volume_change_pct: float
    is_micro_cluster: bool
    labeling_confidence: float
    review_required: bool
    created_at: str
    schema_version: str = SCHEMA_VERSION
    clustering_algorithm: str = CLUSTERING_ALGORITHM
    labeling_model: str                          # set by ThemeLabeler or pipeline
    labeling_prompt_version: str = LABELING_PROMPT_VERSION

    @field_validator("discovery_friction_rate")
    @classmethod
    def validate_friction_rate(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError(f"discovery_friction_rate must be 0.0–1.0, got {v}")
        return round(v, 4)

    @field_validator("avg_sentiment_score")
    @classmethod
    def validate_sentiment_score(cls, v: float) -> float:
        if not (-1.0 <= v <= 1.0):
            raise ValueError(f"avg_sentiment_score must be -1.0–1.0, got {v}")
        return round(v, 4)

    @field_validator("labeling_confidence")
    @classmethod
    def validate_labeling_confidence(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError(f"labeling_confidence must be 0.0–1.0, got {v}")
        return round(v, 4)

    def to_jsonl(self) -> str:
        return self.model_dump_json()

    model_config = {"frozen": True}
