from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_PHASE7_ROOT = Path(__file__).parent
_DEFAULT_DB = _PHASE7_ROOT.parent / "phase-6-storage" / "data" / "knowledge_base.db"
_DEFAULT_CHROMA = _PHASE7_ROOT.parent / "phase-6-storage" / "data" / "chroma"


@dataclass
class Phase7Config:
    db_path: str = str(_DEFAULT_DB)
    chroma_persist_dir: str = str(_DEFAULT_CHROMA)

    anthropic_api_key: Optional[str] = None
    llm_model: str = "claude-sonnet-4-6"

    groq_api_key: Optional[str] = None
    groq_model: str = "llama-3.3-70b-versatile"

    # Ollama has no API key — enabled explicitly via OLLAMA_BASE_URL/OLLAMA_MODEL
    # so the dashboard/API don't silently try a local server that isn't running.
    ollama_enabled: bool = False
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "qwen2.5:3b"

    llm_strategy: str = "failover"  # failover | round_robin — see shared/llm_providers/router.py

    max_evidence_reviews: int = 10
    max_insights_in_context: int = 20
    nl_query_timeout_seconds: int = 30
    min_confidence_score: float = 0.5
    stale_threshold_hours: int = 48

    @classmethod
    def from_env(cls) -> "Phase7Config":
        ollama_url = os.getenv("OLLAMA_BASE_URL", "")
        ollama_model = os.getenv("OLLAMA_MODEL", "")
        return cls(
            db_path=os.getenv("DB_PATH", str(_DEFAULT_DB)),
            chroma_persist_dir=os.getenv("CHROMA_DIR", str(_DEFAULT_CHROMA)),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
            llm_model=os.getenv("LLM_MODEL", "claude-sonnet-4-6"),
            groq_api_key=os.getenv("GROQ_API_KEY"),
            groq_model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            ollama_enabled=bool(ollama_url or ollama_model),
            ollama_base_url=(ollama_url or "http://localhost:11434") + "/v1",
            ollama_model=ollama_model or "qwen2.5:3b",
            llm_strategy=os.getenv("LLM_STRATEGY", "failover"),
            max_evidence_reviews=int(os.getenv("MAX_EVIDENCE_REVIEWS", "10")),
            max_insights_in_context=int(os.getenv("MAX_INSIGHTS_IN_CONTEXT", "20")),
            nl_query_timeout_seconds=int(os.getenv("NL_QUERY_TIMEOUT", "30")),
            min_confidence_score=float(os.getenv("MIN_CONFIDENCE_SCORE", "0.5")),
            stale_threshold_hours=int(os.getenv("STALE_THRESHOLD_HOURS", "48")),
        )
