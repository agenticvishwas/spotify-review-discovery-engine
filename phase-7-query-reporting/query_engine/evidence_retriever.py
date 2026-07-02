from __future__ import annotations
import json
import sqlite3
from typing import Optional


class EvidenceRetriever:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def for_insight(self, insight_id: str, limit: int = 5) -> list[dict]:
        rows = self._conn.execute(
            """SELECT ir.verbatim, ir.review_id, n.platform, n.normalized_rating,
                      n.published_at
               FROM insight_reviews ir
               LEFT JOIN analyzed_reviews a ON ir.review_id = a.id
               LEFT JOIN normalized_reviews n ON a.normalized_review_id = n.id
               WHERE ir.insight_id = ? AND ir.verbatim IS NOT NULL
               LIMIT ?""",
            (insight_id, limit),
        ).fetchall()
        if rows:
            return [dict(r) for r in rows]

        # Fallback: verbatims stored as JSON in insights.supporting_verbatims.
        # This covers rows loaded before insight_loader.py was fixed to write
        # the verbatim text into insight_reviews.verbatim directly.
        row = self._conn.execute(
            "SELECT supporting_verbatims FROM insights WHERE id = ?", (insight_id,)
        ).fetchone()
        if row and row[0]:
            try:
                texts = json.loads(row[0])
            except (json.JSONDecodeError, TypeError):
                return []
            return [
                {"verbatim": t, "platform": "", "normalized_rating": None, "published_at": None}
                for t in texts[:limit] if t
            ]
        return []

    def for_cluster(self, cluster_id: str, limit: int = 5) -> list[dict]:
        rows = self._conn.execute(
            """SELECT n.clean_text AS verbatim, cm.review_id, n.platform,
                      n.normalized_rating, n.published_at, cm.is_representative
               FROM cluster_members cm
               JOIN analyzed_reviews a ON cm.review_id = a.id
               JOIN normalized_reviews n ON a.normalized_review_id = n.id
               WHERE cm.cluster_id = ?
               ORDER BY cm.is_representative DESC, a.confidence_score DESC
               LIMIT ?""",
            (cluster_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def for_review_ids(self, review_ids: list[str], limit: int = 10) -> list[dict]:
        if not review_ids:
            return []
        ids = review_ids[:limit]
        placeholders = ",".join("?" * len(ids))
        rows = self._conn.execute(
            f"""SELECT a.id AS review_id, n.clean_text AS verbatim, n.platform,
                       n.normalized_rating, n.published_at, a.sentiment
                FROM analyzed_reviews a
                JOIN normalized_reviews n ON a.normalized_review_id = n.id
                WHERE a.id IN ({placeholders})""",
            ids,
        ).fetchall()
        return [dict(r) for r in rows]

    def lineage(self, raw_review_id: str) -> Optional[dict]:
        row = self._conn.execute(
            "SELECT * FROM lineage WHERE raw_review_id = ?", (raw_review_id,)
        ).fetchone()
        return dict(row) if row else None

    def discovery_friction_verbatims(self, limit: int = 20) -> list[dict]:
        rows = self._conn.execute(
            """SELECT n.clean_text AS verbatim, n.platform, n.normalized_rating,
                      n.published_at, a.discovery_friction_description, a.sentiment
               FROM analyzed_reviews a
               JOIN normalized_reviews n ON a.normalized_review_id = n.id
               WHERE a.discovery_friction_detected = 1
                 AND a.analysis_status = 'success'
                 AND a.confidence_score >= 0.6
               ORDER BY a.confidence_score DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
