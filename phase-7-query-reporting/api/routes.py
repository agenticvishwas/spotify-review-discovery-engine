"""Phase 7 FastAPI routes — programmatic access to the knowledge base.

Endpoints:
    GET  /api/insights                    All insights, sortable
    GET  /api/insights/{id}               Single insight with evidence
    GET  /api/insights/{id}/evidence      Verbatims for an insight
    GET  /api/clusters                    All clusters
    GET  /api/clusters/{id}/reviews       Reviews in a cluster
    GET  /api/jtbd                        All JTBD profiles
    GET  /api/segments                    User segment profiles
    GET  /api/pipeline-runs               Pipeline run history
    POST /api/query                       NL query endpoint
"""
from __future__ import annotations
import sqlite3
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

_PHASE7_ROOT = Path(__file__).parent.parent
if str(_PHASE7_ROOT) not in sys.path:
    sys.path.insert(0, str(_PHASE7_ROOT))

from config import Phase7Config
from data_freshness import latest_run_cutoff

_config = Phase7Config.from_env()
_conn: Optional[sqlite3.Connection] = None


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(_config.db_path, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode = WAL")
        _conn.execute("PRAGMA cache_size = -32000")
    return _conn


@asynccontextmanager
async def lifespan(app: FastAPI):
    _get_conn()
    yield
    if _conn:
        _conn.close()


app = FastAPI(
    title="Spotify Review Discovery Engine — Phase 7 API",
    version="1.0",
    description="Programmatic access to the product intelligence knowledge base.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _rows(sql: str, params: tuple = ()) -> list[dict]:
    return [dict(r) for r in _get_conn().execute(sql, params).fetchall()]


def _one(sql: str, params: tuple = ()) -> Optional[dict]:
    row = _get_conn().execute(sql, params).fetchone()
    return dict(row) if row else None


# ── Insights ──────────────────────────────────────────────────────────────────

@app.get("/api/insights")
def list_insights(
    insight_type: Optional[str] = None,
    min_opportunity: float = 0.0,
    include_pending: bool = False,
    limit: int = Query(default=50, le=500),
) -> list[dict]:
    sql = "SELECT * FROM insights WHERE 1=1"
    params: list[Any] = []
    cutoff = latest_run_cutoff(_get_conn(), "insights", "generated_at")
    if cutoff:
        sql += " AND generated_at >= ?"
        params.append(cutoff)
    if not include_pending:
        sql += " AND review_required = 0"
    if insight_type:
        sql += " AND insight_type = ?"
        params.append(insight_type)
    if min_opportunity > 0:
        sql += " AND opportunity_score >= ?"
        params.append(min_opportunity)
    sql += " ORDER BY opportunity_score DESC LIMIT ?"
    params.append(limit)
    return _rows(sql, tuple(params))


@app.get("/api/insights/{insight_id}")
def get_insight(insight_id: str) -> dict:
    row = _one("SELECT * FROM insights WHERE id = ?", (insight_id,))
    if not row:
        raise HTTPException(404, "Insight not found")
    clusters = _rows(
        "SELECT cluster_id FROM insight_clusters WHERE insight_id = ?", (insight_id,)
    )
    reviews = _rows(
        "SELECT review_id, verbatim FROM insight_reviews WHERE insight_id = ?", (insight_id,)
    )
    row["supporting_cluster_ids"] = [r["cluster_id"] for r in clusters]
    row["supporting_review_ids"] = [r["review_id"] for r in reviews]
    row["verbatims"] = [r["verbatim"] for r in reviews if r["verbatim"]]
    return row


@app.get("/api/insights/{insight_id}/evidence")
def get_insight_evidence(insight_id: str) -> dict:
    insight = _one("SELECT id, title FROM insights WHERE id = ?", (insight_id,))
    if not insight:
        raise HTTPException(404, "Insight not found")
    verbatims = _rows(
        """SELECT ir.review_id, ir.verbatim, n.platform, n.normalized_rating, n.published_at
           FROM insight_reviews ir
           LEFT JOIN analyzed_reviews a ON ir.review_id = a.id
           LEFT JOIN normalized_reviews n ON a.normalized_review_id = n.id
           WHERE ir.insight_id = ? AND ir.verbatim IS NOT NULL""",
        (insight_id,),
    )
    cluster_ids = [
        r["cluster_id"]
        for r in _rows(
            "SELECT cluster_id FROM insight_clusters WHERE insight_id = ?", (insight_id,)
        )
    ]
    return {
        "insight_id": insight_id,
        "insight_title": insight["title"],
        "cluster_ids": cluster_ids,
        "verbatims": verbatims,
        "verbatim_count": len(verbatims),
    }


# ── Clusters ──────────────────────────────────────────────────────────────────

@app.get("/api/clusters")
def list_clusters(
    discovery_only: bool = False,
    trend: Optional[str] = None,
    limit: int = Query(default=50, le=500),
) -> list[dict]:
    sql = "SELECT * FROM clusters WHERE is_micro_cluster = 0"
    params: list[Any] = []
    cutoff = latest_run_cutoff(_get_conn(), "clusters", "created_at")
    if cutoff:
        sql += " AND created_at >= ?"
        params.append(cutoff)
    if discovery_only:
        sql += " AND is_discovery_related = 1"
    if trend:
        sql += " AND trend_direction = ?"
        params.append(trend)
    sql += " ORDER BY size DESC LIMIT ?"
    params.append(limit)
    return _rows(sql, tuple(params))


@app.get("/api/clusters/{cluster_id}/reviews")
def get_cluster_reviews(
    cluster_id: str,
    representatives_only: bool = False,
    limit: int = Query(default=20, le=200),
) -> list[dict]:
    cluster = _one("SELECT id FROM clusters WHERE id = ?", (cluster_id,))
    if not cluster:
        raise HTTPException(404, "Cluster not found")
    sql = (
        """SELECT n.clean_text AS verbatim, n.platform, n.normalized_rating,
                  n.published_at, cm.is_representative
           FROM cluster_members cm
           JOIN analyzed_reviews a ON cm.review_id = a.id
           JOIN normalized_reviews n ON a.normalized_review_id = n.id
           WHERE cm.cluster_id = ?"""
    )
    params: list[Any] = [cluster_id]
    if representatives_only:
        sql += " AND cm.is_representative = 1"
    sql += " ORDER BY cm.is_representative DESC, a.confidence_score DESC LIMIT ?"
    params.append(limit)
    return _rows(sql, tuple(params))


# ── JTBD ──────────────────────────────────────────────────────────────────────

@app.get("/api/jtbd")
def list_jtbd() -> list[dict]:
    cutoff = latest_run_cutoff(_get_conn(), "jtbd_profiles", "generated_at")
    sql = "SELECT * FROM jtbd_profiles WHERE 1=1"
    params: list[Any] = []
    if cutoff:
        sql += " AND generated_at >= ?"
        params.append(cutoff)
    sql += " ORDER BY gap_score DESC"
    return _rows(sql, tuple(params))


# ── Segments ──────────────────────────────────────────────────────────────────

@app.get("/api/segments")
def list_segments() -> list[dict]:
    cutoff = latest_run_cutoff(_get_conn(), "user_segments", "generated_at")
    sql = "SELECT * FROM user_segments WHERE 1=1"
    params: list[Any] = []
    if cutoff:
        sql += " AND generated_at >= ?"
        params.append(cutoff)
    sql += " ORDER BY fraction_of_total DESC"
    return _rows(sql, tuple(params))


# ── Pipeline runs ─────────────────────────────────────────────────────────────

@app.get("/api/pipeline-runs")
def list_pipeline_runs(limit: int = Query(default=10, le=100)) -> list[dict]:
    return _rows(
        "SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT ?", (limit,)
    )


# ── NL Query ─────────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    question: str
    answer: str
    confidence: str
    key_findings: list[dict]
    caveats: Optional[str]
    related_insights: list[str]
    generated_at: str


@app.post("/api/query", response_model=QueryResponse)
def nl_query(req: QueryRequest) -> dict:
    from query_engine.intent_classifier import IntentClassifier
    from query_engine.query_planner import QueryPlanner
    from query_engine.query_executor import QueryExecutor
    from query_engine.evidence_retriever import EvidenceRetriever
    from query_engine.answer_synthesizer import AnswerSynthesizer
    from query_engine.llm_factory import build_llm_provider

    llm = build_llm_provider(_config)
    if llm is None:
        raise HTTPException(
            503,
            "No LLM provider configured — set ANTHROPIC_API_KEY, GROQ_API_KEY, "
            "or OLLAMA_BASE_URL/OLLAMA_MODEL to enable NL query.",
        )

    conn = _get_conn()
    classified = IntentClassifier().classify(req.question)
    plan = QueryPlanner().build(classified, req.question)
    results = QueryExecutor(conn).execute(plan, raw_question=req.question)

    retriever = EvidenceRetriever(conn)
    verbatims: list[dict] = []
    for step in results["steps"]:
        if step.get("table") == "insights":
            for row in step["rows"][:3]:
                verbatims.extend(retriever.for_insight(row["id"], limit=3))
        elif step.get("table") == "clusters":
            for row in step["rows"][:3]:
                verbatims.extend(retriever.for_cluster(row["id"], limit=3))

    answer = AnswerSynthesizer(llm).synthesize(req.question, results, verbatims)
    return answer
