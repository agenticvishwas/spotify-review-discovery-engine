"""Cached database helpers for Streamlit pages.

All functions use st.cache_resource / st.cache_data so the SQLite connection
is shared across reruns and query results are cached with a short TTL.
"""
from __future__ import annotations
import json
import os
import sqlite3
from pathlib import Path

import streamlit as st

from data_freshness import latest_run_cutoff

_DEFAULT_DB = (
    Path(__file__).parent.parent.parent / "phase-6-storage" / "data" / "knowledge_base.db"
)

# Phase 5 writes "..." as a sentinel when LLM generation fails.
# Strip it before rendering so PMs don't see raw failure tokens.
def clean_description(text: str | None) -> str | None:
    if not text:
        return None
    stripped = text.lstrip(".").strip()
    if not stripped or stripped in ("Theme labeling failed", "LLM description unavailable"):
        return None
    return stripped


@st.cache_resource
def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    path = db_path or os.getenv("DB_PATH", str(_DEFAULT_DB))
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA cache_size = -32000")
    return conn


@st.cache_data(ttl=300)
def fetch_overview_stats(_db: str | None = None) -> dict:
    conn = get_connection(_db)
    s: dict = {}

    s["total_reviews"] = conn.execute(
        "SELECT COUNT(*) FROM normalized_reviews"
    ).fetchone()[0]

    s["friction_reviews"] = conn.execute(
        "SELECT COUNT(*) FROM analyzed_reviews "
        "WHERE discovery_friction_detected=1 AND analysis_status='success'"
    ).fetchone()[0]

    insight_cutoff = latest_run_cutoff(conn, "insights", "generated_at")
    s["total_insights"] = conn.execute(
        "SELECT COUNT(*) FROM insights WHERE review_required=0 AND generated_at >= ?",
        (insight_cutoff or "",),
    ).fetchone()[0]

    cluster_cutoff = latest_run_cutoff(conn, "clusters", "created_at")
    s["total_clusters"] = conn.execute(
        "SELECT COUNT(*) FROM clusters WHERE is_micro_cluster=0 AND created_at >= ?",
        (cluster_cutoff or "",),
    ).fetchone()[0]

    s["by_platform"] = {
        r[0]: r[1]
        for r in conn.execute(
            "SELECT platform, COUNT(*) FROM normalized_reviews GROUP BY platform"
        ).fetchall()
    }

    s["by_sentiment"] = {
        r[0]: r[1]
        for r in conn.execute(
            "SELECT sentiment, COUNT(*) FROM analyzed_reviews "
            "WHERE analysis_status='success' GROUP BY sentiment"
        ).fetchall()
    }

    row = conn.execute(
        "SELECT MAX(completed_at) FROM pipeline_runs WHERE status='completed'"
    ).fetchone()
    s["last_successful_run"] = row[0] if row else None
    s["friction_rate"] = (
        round(s["friction_reviews"] / s["total_reviews"] * 100, 1)
        if s["total_reviews"] > 0 else 0.0
    )
    return s


@st.cache_data(ttl=300)
def fetch_insights(
    _db: str | None = None,
    review_required: int | None = 0,
    insight_type: str | None = None,
    min_opportunity: float = 0.0,
    limit: int = 100,
) -> list[dict]:
    conn = get_connection(_db)
    sql = "SELECT * FROM insights WHERE 1=1"
    params: list = []
    cutoff = latest_run_cutoff(conn, "insights", "generated_at")
    if cutoff:
        sql += " AND generated_at >= ?"
        params.append(cutoff)
    if review_required is not None:
        sql += " AND review_required = ?"
        params.append(review_required)
    if insight_type:
        sql += " AND insight_type = ?"
        params.append(insight_type)
    if min_opportunity > 0:
        sql += " AND opportunity_score >= ?"
        params.append(min_opportunity)
    sql += " ORDER BY opportunity_score DESC LIMIT ?"
    params.append(limit)
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


@st.cache_data(ttl=300)
def fetch_clusters(_db: str | None = None, discovery_only: bool = False) -> list[dict]:
    conn = get_connection(_db)
    sql = "SELECT * FROM clusters WHERE is_micro_cluster=0"
    params: list = []
    cutoff = latest_run_cutoff(conn, "clusters", "created_at")
    if cutoff:
        sql += " AND created_at >= ?"
        params.append(cutoff)
    if discovery_only:
        sql += " AND is_discovery_related=1"
    sql += " ORDER BY size DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


@st.cache_data(ttl=300)
def fetch_jtbd(_db: str | None = None) -> list[dict]:
    conn = get_connection(_db)
    sql = "SELECT * FROM jtbd_profiles WHERE 1=1"
    params: list = []
    cutoff = latest_run_cutoff(conn, "jtbd_profiles", "generated_at")
    if cutoff:
        sql += " AND generated_at >= ?"
        params.append(cutoff)
    sql += " ORDER BY gap_score DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


@st.cache_data(ttl=300)
def fetch_segments(_db: str | None = None) -> list[dict]:
    conn = get_connection(_db)
    # Use latest row per segment_label so an incomplete pipeline re-run
    # doesn't hide segments that weren't regenerated in that run.
    rows = conn.execute(
        """SELECT * FROM user_segments s1
           WHERE generated_at = (
               SELECT MAX(s2.generated_at) FROM user_segments s2
               WHERE s2.segment_label = s1.segment_label
           )
           ORDER BY fraction_of_total DESC"""
    ).fetchall()
    return [dict(r) for r in rows]


@st.cache_data(ttl=60)
def fetch_insight_evidence(insight_id: str, _db: str | None = None) -> dict:
    conn = get_connection(_db)
    clusters = conn.execute(
        "SELECT cluster_id FROM insight_clusters WHERE insight_id=?", (insight_id,)
    ).fetchall()
    reviews = conn.execute(
        """SELECT ir.review_id, ir.verbatim, n.platform, n.normalized_rating,
                  n.published_at
           FROM insight_reviews ir
           LEFT JOIN analyzed_reviews a ON ir.review_id = a.id
           LEFT JOIN normalized_reviews n ON a.normalized_review_id = n.id
           WHERE ir.insight_id = ?""",
        (insight_id,),
    ).fetchall()
    verbatims = [dict(r) for r in reviews if r["verbatim"]]

    # Fallback: insight_reviews.verbatim was stored as NULL by the original
    # Phase 6 loader — read verbatim text from insights.supporting_verbatims instead.
    if not verbatims:
        row = conn.execute(
            "SELECT supporting_verbatims FROM insights WHERE id = ?", (insight_id,)
        ).fetchone()
        if row and row[0]:
            try:
                texts = json.loads(row[0])
                verbatims = [
                    {"verbatim": t, "platform": "", "normalized_rating": None, "published_at": None}
                    for t in texts if t
                ]
            except (json.JSONDecodeError, TypeError):
                pass

    return {
        "cluster_ids": [r[0] for r in clusters],
        "verbatims": verbatims,
    }


@st.cache_data(ttl=60)
def fetch_cluster_evidence(cluster_id: str, _db: str | None = None, limit: int = 10) -> list[dict]:
    conn = get_connection(_db)
    rows = conn.execute(
        """SELECT n.clean_text AS verbatim, n.platform, n.normalized_rating,
                  n.published_at, cm.is_representative
           FROM cluster_members cm
           JOIN analyzed_reviews a ON cm.review_id = a.id
           JOIN normalized_reviews n ON a.normalized_review_id = n.id
           WHERE cm.cluster_id = ?
           ORDER BY cm.is_representative DESC, a.confidence_score DESC
           LIMIT ?""",
        (cluster_id, limit),
    ).fetchall()
    return [dict(r) for r in rows]


@st.cache_data(ttl=300)
def fetch_discovery_trend(_db: str | None = None) -> list[dict]:
    conn = get_connection(_db)
    rows = conn.execute(
        """SELECT DATE(n.published_at) AS day,
                  COUNT(*) AS total,
                  SUM(a.discovery_friction_detected) AS friction
           FROM analyzed_reviews a
           JOIN normalized_reviews n ON a.normalized_review_id = n.id
           WHERE a.analysis_status = 'success'
             AND n.published_at IS NOT NULL
           GROUP BY day
           ORDER BY day""",
    ).fetchall()
    return [dict(r) for r in rows]
