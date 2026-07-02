from typing import Optional
from pydantic import BaseModel, Field


class PlatformStats(BaseModel):
    fetched: int = 0
    valid: int = 0
    rejected: int = 0
    rejection_reasons: dict[str, int] = Field(default_factory=dict)

    def record_rejection(self, reason: str) -> None:
        self.rejected += 1
        self.rejection_reasons[reason] = self.rejection_reasons.get(reason, 0) + 1

    model_config = {"frozen": False}


class IngestionBatch(BaseModel):
    batch_id: str
    platform: str
    started_at: str
    query_params: dict = Field(default_factory=dict)
    completed_at: Optional[str] = None
    total_fetched: int = 0
    total_valid: int = 0
    total_rejected: int = 0
    status: str = "running"  # running | completed | partial | failed
    failure_reason: Optional[str] = None

    model_config = {"frozen": False}
