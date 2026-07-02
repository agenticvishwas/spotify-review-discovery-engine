import uuid
from datetime import datetime, timezone
from typing import Optional, Literal

from pydantic import BaseModel, field_validator, model_validator

VALID_PLATFORMS = frozenset({"app_store", "google_play", "reddit", "community", "social"})
SCHEMA_VERSION = "1.0"

# Stable UUID namespace for deterministic ID generation
_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def make_stable_id(platform: str, author: Optional[str], date: str, text: str) -> str:
    """Deterministic UUID5 based on platform + author + date + first 50 chars of text.

    Running twice with identical inputs returns the same UUID — ensures idempotency.
    """
    key = f"{platform}|{author or ''}|{date}|{text[:50]}"
    return str(uuid.uuid5(_NAMESPACE, key))


class RawReview(BaseModel):
    id: str
    source_platform: str
    raw_text: str
    published_at: str
    source_url: str
    ingested_at: str
    ingestion_batch_id: str
    rating: Optional[int] = None
    author_id: Optional[str] = None
    schema_version: str = SCHEMA_VERSION

    @field_validator("source_platform")
    @classmethod
    def validate_platform(cls, v: str) -> str:
        if v not in VALID_PLATFORMS:
            raise ValueError(f"source_platform must be one of {VALID_PLATFORMS}, got '{v}'")
        return v

    @field_validator("raw_text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("raw_text must not be empty")
        return v

    @field_validator("rating")
    @classmethod
    def validate_rating(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not (1 <= v <= 5):
            raise ValueError(f"rating must be 1–5, got {v}")
        return v

    @field_validator("published_at", "ingested_at")
    @classmethod
    def validate_non_empty_date(cls, v: str) -> str:
        if not v:
            raise ValueError("date field must not be empty")
        return v

    def validation_errors(self) -> list[str]:
        """Return human-readable rejection reasons without raising. Used by the pipeline."""
        errors: list[str] = []
        if not self.raw_text or not self.raw_text.strip():
            errors.append("empty_text")
        if not self.source_platform:
            errors.append("missing_platform")
        elif self.source_platform not in VALID_PLATFORMS:
            errors.append("invalid_platform")
        if not self.published_at:
            errors.append("missing_date")
        if self.rating is not None and not (1 <= self.rating <= 5):
            errors.append("invalid_rating")
        return errors

    def to_jsonl(self) -> str:
        return self.model_dump_json()

    model_config = {"frozen": True}
