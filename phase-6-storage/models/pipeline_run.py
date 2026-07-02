from __future__ import annotations
import json
import uuid
from datetime import datetime, timezone
from typing import Literal, Optional
from pydantic import BaseModel, Field


class PipelineRun(BaseModel):
    model_config = {"frozen": False}

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    started_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None
    status: Literal["running", "completed", "failed", "partial"] = "running"

    phase1_loaded: bool = False
    phase2_loaded: bool = False
    phase3_loaded: bool = False
    phase4_loaded: bool = False
    phase5_loaded: bool = False

    raw_review_count: int = 0
    normalized_review_count: int = 0
    analyzed_review_count: int = 0
    cluster_count: int = 0
    insight_count: int = 0

    error_log: list[str] = Field(default_factory=list)
    schema_version: str = "1.0"

    def finish(self, status: Literal["completed", "failed", "partial"] = "completed") -> None:
        self.status = status
        self.completed_at = datetime.now(timezone.utc).isoformat()

    def add_error(self, msg: str) -> None:
        self.error_log.append(msg)

    def to_db_dict(self) -> dict:
        return {
            "id": self.id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "status": self.status,
            "phase1_loaded": int(self.phase1_loaded),
            "phase2_loaded": int(self.phase2_loaded),
            "phase3_loaded": int(self.phase3_loaded),
            "phase4_loaded": int(self.phase4_loaded),
            "phase5_loaded": int(self.phase5_loaded),
            "raw_review_count": self.raw_review_count,
            "normalized_review_count": self.normalized_review_count,
            "analyzed_review_count": self.analyzed_review_count,
            "cluster_count": self.cluster_count,
            "insight_count": self.insight_count,
            "error_log": json.dumps(self.error_log),
            "schema_version": self.schema_version,
        }
