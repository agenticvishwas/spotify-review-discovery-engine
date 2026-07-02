from typing import Optional
from pydantic import BaseModel, Field


class PreprocessingBatch(BaseModel):
    batch_id: str
    source_batch_ids: list[str] = Field(default_factory=list)
    started_at: str
    completed_at: Optional[str] = None
    total_input: int = 0
    total_output: int = 0
    filtered_non_english: int = 0
    filtered_duplicates: int = 0
    filtered_low_quality: int = 0
    status: str = "running"  # running | completed | failed

    model_config = {"frozen": False}
