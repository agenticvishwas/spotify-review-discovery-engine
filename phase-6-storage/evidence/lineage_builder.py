from __future__ import annotations
import json
import logging
import sqlite3

logger = logging.getLogger(__name__)

_CHUNK = 500


class LineageBuilder:
    """
    Builds the lineage table:
      raw_review → normalized_review → analyzed_review → [clusters] → [insights]

    This denormalized cache lets Phase 7 answer "show me all insights for this review"
    in a single lookup instead of six joins.
    """

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def build(self) -> int:
        """
        Rebuilds the full lineage table.
        Returns number of lineage rows written.
        """
        logger.info("Building lineage table...")
        self._conn.execute("DELETE FROM lineage")
        self._conn.commit()

        # raw_id → normalized_id
        norm_map = self._build_norm_map()
        # normalized_id → analyzed_id
        analyzed_map = self._build_analyzed_map()
        # review_id → [cluster_ids]
        cluster_map = self._build_cluster_map()
        # review_id → [insight_ids]
        insight_map = self._build_insight_map()

        rows: list[dict] = []
        for raw_id, norm_id in norm_map.items():
            analyzed_id = analyzed_map.get(norm_id)
            rows.append({
                "raw_review_id": raw_id,
                "normalized_review_id": norm_id,
                "analyzed_review_id": analyzed_id,
                "cluster_ids": json.dumps(cluster_map.get(norm_id, [])),
                "insight_ids": json.dumps(insight_map.get(norm_id, [])),
            })

        cols = list(rows[0].keys()) if rows else []
        if rows:
            ph = ", ".join("?" * len(cols))
            sql = f"INSERT OR REPLACE INTO lineage ({', '.join(cols)}) VALUES ({ph})"
            for i in range(0, len(rows), _CHUNK):
                chunk = rows[i: i + _CHUNK]
                self._conn.executemany(sql, [tuple(r[c] for c in cols) for r in chunk])
            self._conn.commit()

        logger.info("Lineage built: %d rows", len(rows))
        return len(rows)

    def get_lineage(self, raw_review_id: str) -> dict:
        row = self._conn.execute(
            "SELECT * FROM lineage WHERE raw_review_id = ?", (raw_review_id,)
        ).fetchone()
        if not row:
            return {}
        d = dict(row)
        d["cluster_ids"] = json.loads(d.get("cluster_ids") or "[]")
        d["insight_ids"] = json.loads(d.get("insight_ids") or "[]")
        return d

    def get_review_insights(self, raw_review_id: str) -> list[str]:
        row = self._conn.execute(
            "SELECT insight_ids FROM lineage WHERE raw_review_id = ?", (raw_review_id,)
        ).fetchone()
        if not row:
            return []
        return json.loads(row["insight_ids"] or "[]")

    # ------------------------------------------------------------------
    # Private map builders
    # ------------------------------------------------------------------
    def _build_norm_map(self) -> dict[str, str]:
        rows = self._conn.execute(
            "SELECT source_review_id, id FROM normalized_reviews"
        ).fetchall()
        return {r["source_review_id"]: r["id"] for r in rows}

    def _build_analyzed_map(self) -> dict[str, str]:
        rows = self._conn.execute(
            "SELECT normalized_review_id, id FROM analyzed_reviews WHERE analysis_status = 'success'"
        ).fetchall()
        return {r["normalized_review_id"]: r["id"] for r in rows}

    def _build_cluster_map(self) -> dict[str, list[str]]:
        rows = self._conn.execute(
            "SELECT review_id, cluster_id FROM cluster_members"
        ).fetchall()
        result: dict[str, list[str]] = {}
        for r in rows:
            result.setdefault(r["review_id"], []).append(r["cluster_id"])
        return result

    def _build_insight_map(self) -> dict[str, list[str]]:
        rows = self._conn.execute(
            "SELECT review_id, insight_id FROM insight_reviews"
        ).fetchall()
        result: dict[str, list[str]] = {}
        for r in rows:
            result.setdefault(r["review_id"], []).append(r["insight_id"])
        return result
