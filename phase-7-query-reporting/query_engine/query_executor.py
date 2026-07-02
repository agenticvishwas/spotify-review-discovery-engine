from __future__ import annotations
import logging
import sqlite3
from typing import Any, Optional
from .query_planner import QueryPlan, QueryStep
from data_freshness import latest_run_cutoff

logger = logging.getLogger(__name__)

# Tables whose rows accumulate across pipeline re-runs without being
# deduplicated (see data_freshness.py) — scope NL-query results to the
# latest run so answers aren't padded with stale duplicate evidence.
_FRESHNESS_TS_COLUMN = {
    "clusters": "created_at",
    "insights": "generated_at",
    "jtbd_profiles": "generated_at",
    "user_segments": "generated_at",
}


class QueryExecutor:
    def __init__(self, conn: sqlite3.Connection, chroma_client: Any = None):
        self._conn = conn
        self._chroma = chroma_client

    def execute(self, plan: QueryPlan, raw_question: str = "") -> dict[str, Any]:
        results: dict[str, Any] = {"intent": plan.intent, "steps": []}
        for step in plan.steps:
            if step.kind == "sql":
                rows = self._run_sql(step)
            elif step.kind == "vector_search":
                rows = self._run_vector(raw_question, step.limit)
            else:
                rows = []
            results["steps"].append({
                "description": step.description,
                "kind": step.kind,
                "table": step.table,
                "rows": rows,
                "count": len(rows),
            })
        return results

    def _run_sql(self, step: QueryStep) -> list[dict]:
        table = step.table
        where: list[str] = []
        params: list[Any] = []
        f = step.filters

        if table == "analyzed_reviews":
            if f.get("discovery_friction_detected"):
                where.append("discovery_friction_detected = 1")
            if f.get("min_confidence"):
                where.append("confidence_score >= ?")
                params.append(f["min_confidence"])
            if f.get("user_segment_signal"):
                where.append("user_segment_signal = ?")
                params.append(f["user_segment_signal"])
            if f.get("feature_mention"):
                where.append("feature_mentions LIKE ?")
                params.append(f"%{f['feature_mention']}%")
            where.append("analysis_status = 'success'")

        elif table == "clusters":
            if f.get("is_discovery_related"):
                where.append("is_discovery_related = 1")
            if "is_micro_cluster" in f:
                where.append("is_micro_cluster = ?")
                params.append(f["is_micro_cluster"])
            if f.get("trend_direction"):
                where.append("trend_direction = ?")
                params.append(f["trend_direction"])

        elif table == "insights":
            if "review_required" in f:
                where.append("review_required = ?")
                params.append(f["review_required"])
            if f.get("discovery_friction_related"):
                where.append("discovery_friction_related = 1")
            if f.get("trend_direction"):
                where.append("trend_direction = ?")
                params.append(f["trend_direction"])

        elif table == "user_segments":
            if f.get("segment_label"):
                where.append("segment_label = ?")
                params.append(f["segment_label"])

        ts_column = _FRESHNESS_TS_COLUMN.get(table)
        if ts_column:
            cutoff = latest_run_cutoff(self._conn, table, ts_column)
            if cutoff:
                where.append(f"{ts_column} >= ?")
                params.append(cutoff)

        sql = f"SELECT * FROM {table}"
        if where:
            sql += " WHERE " + " AND ".join(where)
        if step.order_by:
            sql += f" ORDER BY {step.order_by}"
        sql += f" LIMIT {step.limit}"

        try:
            rows = self._conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        except Exception as exc:
            logger.error("sql_step_failed table=%s error=%s", table, exc)
            return []

    def _run_vector(self, question: str, limit: int) -> list[dict]:
        if not self._chroma or not question:
            return []
        try:
            collection = self._chroma.get_or_create_collection("reviews")
            results = collection.query(query_texts=[question], n_results=min(limit, 10))
            out = []
            if results and results.get("ids"):
                for i, doc_id in enumerate(results["ids"][0]):
                    out.append({
                        "id": doc_id,
                        "document": (results.get("documents") or [[]])[0][i] if results.get("documents") else "",
                        "distance": (results.get("distances") or [[]])[0][i] if results.get("distances") else None,
                    })
            return out
        except Exception as exc:
            logger.warning("vector_search_failed error=%s", exc)
            return []
