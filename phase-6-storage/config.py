from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Literal, Optional


@dataclass
class StorageConfig:
    # Database
    db_type: Literal["sqlite", "postgresql"] = "sqlite"
    db_path: str = "data/knowledge_base.db"
    pg_dsn: Optional[str] = None

    # Vector store
    chroma_persist_dir: str = "data/chroma"
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_batch_size: int = 512

    # Phase data directories (relative to phase-6-storage/)
    phase1_data_dir: str = "../phase-1-data-ingestion/data/raw_reviews"
    phase2_data_dir: str = "../phase-2-preprocessing/data/normalized_reviews"
    phase3_data_dir: str = "../phase-3-ai-analysis/data/analyzed_reviews"
    phase4_data_dir: str = "../phase-4-clustering/data/clusters"
    phase5_data_dir: str = "../phase-5-insight-generation/data/insights"

    schema_version: str = "1.0"

    @classmethod
    def from_env(cls) -> "StorageConfig":
        return cls(
            db_type=os.getenv("DB_TYPE", "sqlite"),  # type: ignore[arg-type]
            db_path=os.getenv("DB_PATH", "data/knowledge_base.db"),
            pg_dsn=os.getenv("DATABASE_URL"),
            chroma_persist_dir=os.getenv("CHROMA_DIR", "data/chroma"),
            embedding_model=os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
            embedding_batch_size=int(os.getenv("EMBEDDING_BATCH_SIZE", "512")),
            phase1_data_dir=os.getenv("PHASE1_DATA_DIR", "../phase-1-data-ingestion/data/raw_reviews"),
            phase2_data_dir=os.getenv("PHASE2_DATA_DIR", "../phase-2-preprocessing/data/normalized_reviews"),
            phase3_data_dir=os.getenv("PHASE3_DATA_DIR", "../phase-3-ai-analysis/data/analyzed_reviews"),
            phase4_data_dir=os.getenv("PHASE4_DATA_DIR", "../phase-4-clustering/data/clusters"),
            phase5_data_dir=os.getenv("PHASE5_DATA_DIR", "../phase-5-insight-generation/data/insights"),
        )
