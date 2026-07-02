from typing import Optional
from pydantic import BaseModel, field_validator

VALID_PLATFORMS = frozenset({"app_store", "google_play", "reddit", "community", "social"})
SCHEMA_VERSION = "1.0"
QUALITY_THRESHOLD = 0.3


class NormalizedReview(BaseModel):
    id: str
    source_review_id: str
    clean_text: str
    normalized_rating: Optional[float] = None
    language: str
    word_count: int
    sentence_count: int
    quality_score: float
    is_duplicate: bool
    duplicate_of_id: Optional[str] = None
    platform: str
    published_at: str
    normalized_at: str
    schema_version: str = SCHEMA_VERSION
    filters_applied: list[str] = []

    @field_validator("platform")
    @classmethod
    def validate_platform(cls, v: str) -> str:
        if v not in VALID_PLATFORMS:
            raise ValueError(f"platform must be one of {VALID_PLATFORMS}, got '{v}'")
        return v

    @field_validator("normalized_rating")
    @classmethod
    def validate_rating(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (1.0 <= v <= 5.0):
            raise ValueError(f"normalized_rating must be 1.0–5.0, got {v}")
        return v

    @field_validator("quality_score")
    @classmethod
    def validate_quality_score(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError(f"quality_score must be 0.0–1.0, got {v}")
        return v

    @property
    def passes_quality_threshold(self) -> bool:
        return self.quality_score >= QUALITY_THRESHOLD

    def to_jsonl(self) -> str:
        return self.model_dump_json()

    model_config = {"frozen": True}
