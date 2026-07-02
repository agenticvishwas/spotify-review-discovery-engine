from __future__ import annotations
import sqlite3
from typing import Optional
from .base import upsert_batch


class ClusterRepository:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def upsert_clusters(self, rows: list[dict]) -> int:
        return upsert_batch(self._conn, "clusters", rows)

    def upsert_members(self, rows: list[dict]) -> int:
        return upsert_batch(self._conn, "cluster_members", rows)

    def get_by_id(self, cluster_id: str) -> Optional[dict]:
        row = self._conn.execute(
            "SELECT * FROM clusters WHERE id = ?", (cluster_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_members(self, cluster_id: str, representatives_only: bool = False) -> list[str]:
        sql = "SELECT review_id FROM cluster_members WHERE cluster_id = ?"
        params: tuple = (cluster_id,)
        if representatives_only:
            sql += " AND is_representative = 1"
        rows = self._conn.execute(sql, params).fetchall()
        return [r["review_id"] for r in rows]

    def find_discovery_clusters(self, min_friction_rate: float = 0.3) -> list[dict]:
        rows = self._conn.execute(
            """SELECT * FROM clusters
               WHERE discovery_friction_rate >= ?
                 AND is_micro_cluster = 0
               ORDER BY discovery_friction_rate DESC""",
            (min_friction_rate,),
        ).fetchall()
        return [dict(r) for r in rows]

    def trending(self, direction: str = "increasing") -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM clusters WHERE trend_direction = ? AND is_micro_cluster = 0 ORDER BY size DESC",
            (direction,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_clusters_for_review(self, review_id: str) -> list[str]:
        rows = self._conn.execute(
            "SELECT cluster_id FROM cluster_members WHERE review_id = ?", (review_id,)
        ).fetchall()
        return [r["cluster_id"] for r in rows]

    def summary_stats(self) -> dict:
        row = self._conn.execute(
            """SELECT COUNT(*) as total,
                      SUM(CASE WHEN is_micro_cluster = 0 THEN 1 ELSE 0 END) as actionable,
                      AVG(discovery_friction_rate) as avg_friction,
                      AVG(avg_sentiment_score) as avg_sentiment
               FROM clusters"""
        ).fetchone()
        return dict(row) if row else {}
