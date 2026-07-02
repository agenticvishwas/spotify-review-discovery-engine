from __future__ import annotations
import sqlite3
from typing import Optional
from .base import upsert_batch


class InsightRepository:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------
    def upsert_insights(self, rows: list[dict]) -> int:
        return upsert_batch(self._conn, "insights", rows)

    def upsert_insight_clusters(self, rows: list[dict]) -> int:
        return upsert_batch(self._conn, "insight_clusters", rows)

    def upsert_insight_reviews(self, rows: list[dict]) -> int:
        return upsert_batch(self._conn, "insight_reviews", rows)

    def upsert_jtbd(self, rows: list[dict]) -> int:
        return upsert_batch(self._conn, "jtbd_profiles", rows)

    def upsert_segments(self, rows: list[dict]) -> int:
        return upsert_batch(self._conn, "user_segments", rows)

    def upsert_unmet_needs(self, rows: list[dict]) -> int:
        return upsert_batch(self._conn, "unmet_needs", rows)

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------
    def get_by_id(self, insight_id: str) -> Optional[dict]:
        row = self._conn.execute(
            "SELECT * FROM insights WHERE id = ?", (insight_id,)
        ).fetchone()
        return dict(row) if row else None

    def find_by_type(self, insight_type: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM insights WHERE insight_type = ? ORDER BY opportunity_score DESC",
            (insight_type,),
        ).fetchall()
        return [dict(r) for r in rows]

    def find_high_confidence(self, min_score: float = 0.7) -> list[dict]:
        rows = self._conn.execute(
            """SELECT * FROM insights
               WHERE confidence_score >= ? AND review_required = 0
               ORDER BY opportunity_score DESC""",
            (min_score,),
        ).fetchall()
        return [dict(r) for r in rows]

    def find_pending_review(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM insights WHERE review_required = 1 ORDER BY opportunity_score DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def find_friction_insights(self) -> list[dict]:
        rows = self._conn.execute(
            """SELECT * FROM insights
               WHERE discovery_friction_related = 1
               ORDER BY severity_score DESC""",
        ).fetchall()
        return [dict(r) for r in rows]

    def get_evidence(self, insight_id: str) -> dict:
        clusters = self._conn.execute(
            "SELECT cluster_id FROM insight_clusters WHERE insight_id = ?", (insight_id,)
        ).fetchall()
        reviews = self._conn.execute(
            "SELECT review_id, verbatim FROM insight_reviews WHERE insight_id = ?", (insight_id,)
        ).fetchall()
        return {
            "cluster_ids": [r["cluster_id"] for r in clusters],
            "review_ids": [r["review_id"] for r in reviews],
            "verbatims": [r["verbatim"] for r in reviews if r["verbatim"]],
        }

    def top_opportunities(self, limit: int = 20) -> list[dict]:
        rows = self._conn.execute(
            """SELECT * FROM insights
               WHERE review_required = 0
               ORDER BY opportunity_score DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def insight_summary(self) -> dict:
        row = self._conn.execute(
            """SELECT COUNT(*) as total,
                      SUM(CASE WHEN review_required = 0 THEN 1 ELSE 0 END) as ready,
                      SUM(CASE WHEN review_required = 1 THEN 1 ELSE 0 END) as pending,
                      AVG(confidence_score) as avg_confidence,
                      AVG(opportunity_score) as avg_opportunity
               FROM insights"""
        ).fetchone()
        return dict(row) if row else {}
