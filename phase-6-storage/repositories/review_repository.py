from __future__ import annotations
import sqlite3
from typing import Optional
from .base import upsert_batch


class ReviewRepository:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    # ------------------------------------------------------------------
    # Writes (idempotent upserts)
    # ------------------------------------------------------------------
    def upsert_raw(self, rows: list[dict]) -> int:
        return upsert_batch(self._conn, "raw_reviews", rows)

    def upsert_normalized(self, rows: list[dict]) -> int:
        return upsert_batch(self._conn, "normalized_reviews", rows)

    def upsert_analyzed(self, rows: list[dict]) -> int:
        return upsert_batch(self._conn, "analyzed_reviews", rows)

    # ------------------------------------------------------------------
    # Reads — used by Phase 7 query layer
    # ------------------------------------------------------------------
    def get_raw_by_id(self, review_id: str) -> Optional[dict]:
        row = self._conn.execute(
            "SELECT * FROM raw_reviews WHERE id = ?", (review_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_normalized_by_id(self, review_id: str) -> Optional[dict]:
        row = self._conn.execute(
            "SELECT * FROM normalized_reviews WHERE id = ?", (review_id,)
        ).fetchone()
        return dict(row) if row else None

    def find_by_platform(self, platform: str, limit: int = 1000) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM normalized_reviews WHERE platform = ? LIMIT ?",
            (platform, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def find_with_friction(self, min_confidence: float = 0.5) -> list[dict]:
        rows = self._conn.execute(
            """SELECT a.*, n.clean_text, n.platform
               FROM analyzed_reviews a
               JOIN normalized_reviews n ON a.normalized_review_id = n.id
               WHERE a.discovery_friction_detected = 1
                 AND a.confidence_score >= ?
                 AND a.analysis_status = 'success'
               ORDER BY a.confidence_score DESC""",
            (min_confidence,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_analyzed_by_segment(self, segment: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM analyzed_reviews WHERE user_segment_signal = ? AND analysis_status = 'success'",
            (segment,),
        ).fetchall()
        return [dict(r) for r in rows]

    def count_by_platform(self) -> dict[str, int]:
        rows = self._conn.execute(
            "SELECT platform, COUNT(*) as cnt FROM normalized_reviews GROUP BY platform"
        ).fetchall()
        return {r["platform"]: r["cnt"] for r in rows}

    def sentiment_distribution(self) -> dict[str, int]:
        rows = self._conn.execute(
            "SELECT sentiment, COUNT(*) as cnt FROM analyzed_reviews WHERE analysis_status='success' GROUP BY sentiment"
        ).fetchall()
        return {r["sentiment"]: r["cnt"] for r in rows}
