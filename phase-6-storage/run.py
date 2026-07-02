"""
Phase 6 — Storage & Knowledge Base
===================================
Loads all pipeline outputs (Phases 1-5) into:
  - SQLite knowledge base  (data/knowledge_base.db)
  - ChromaDB vector store  (data/chroma/)
  - Lineage table          (within SQLite)

Usage:
  python run.py                        # default config
  python run.py --skip-vectors         # DB only, skip embedding generation
  python run.py --db-path custom.db    # override DB path
  python run.py --only-phase 3         # reload only one phase
"""
from __future__ import annotations
import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from config import StorageConfig
from db.connection import DatabaseManager
from evidence.lineage_builder import LineageBuilder
from loaders import (
    AnalyzedLoader,
    ClusterLoader,
    InsightLoader,
    NormalizedLoader,
    RawReviewLoader,
)
from models.pipeline_run import PipelineRun
from repositories.base import save_pipeline_run
from repositories.cluster_repository import ClusterRepository
from repositories.insight_repository import InsightRepository
from repositories.review_repository import ReviewRepository
from vector_store.chroma_manager import ChromaManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  phase=6  %(levelname)s  %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Phase loaders
# ---------------------------------------------------------------------------

def load_phase1(cfg: StorageConfig, db: DatabaseManager, run: PipelineRun, only: int | None) -> None:
    if only is not None and only != 1:
        return
    t0 = time.time()
    loader = RawReviewLoader(cfg.phase1_data_dir)
    records, skipped = loader.load_all()
    repo = ReviewRepository(db.conn)
    n = repo.upsert_raw(records)
    run.raw_review_count = n
    run.phase1_loaded = True
    logger.info("phase=1 records=%d skipped=%d duration_ms=%d", n, skipped, int((time.time() - t0) * 1000))


def load_phase2(cfg: StorageConfig, db: DatabaseManager, run: PipelineRun, only: int | None) -> None:
    if only is not None and only != 2:
        return
    t0 = time.time()
    loader = NormalizedLoader(cfg.phase2_data_dir)
    records, skipped = loader.load_all()
    repo = ReviewRepository(db.conn)
    n = repo.upsert_normalized(records)
    run.normalized_review_count = n
    run.phase2_loaded = True
    logger.info("phase=2 records=%d skipped=%d duration_ms=%d", n, skipped, int((time.time() - t0) * 1000))


def load_phase3(cfg: StorageConfig, db: DatabaseManager, run: PipelineRun, only: int | None) -> None:
    if only is not None and only != 3:
        return
    t0 = time.time()
    loader = AnalyzedLoader(cfg.phase3_data_dir)
    records, skipped = loader.load_all()
    repo = ReviewRepository(db.conn)
    n = repo.upsert_analyzed(records)
    run.analyzed_review_count = n
    run.phase3_loaded = True
    logger.info("phase=3 records=%d skipped=%d duration_ms=%d", n, skipped, int((time.time() - t0) * 1000))


def load_phase4(cfg: StorageConfig, db: DatabaseManager, run: PipelineRun, only: int | None) -> None:
    if only is not None and only != 4:
        return
    t0 = time.time()
    loader = ClusterLoader(cfg.phase4_data_dir)
    result = loader.load_all()
    clusters, members, skipped = result  # type: ignore[misc]
    repo = ClusterRepository(db.conn)
    nc = repo.upsert_clusters(clusters)
    nm = repo.upsert_members(members)
    run.cluster_count = nc
    run.phase4_loaded = True
    logger.info("phase=4 clusters=%d members=%d skipped=%d duration_ms=%d",
                nc, nm, skipped, int((time.time() - t0) * 1000))


def load_phase5(cfg: StorageConfig, db: DatabaseManager, run: PipelineRun, only: int | None) -> None:
    if only is not None and only != 5:
        return
    t0 = time.time()
    loader = InsightLoader(cfg.phase5_data_dir)
    repo = InsightRepository(db.conn)

    insights, ic_rows, ir_rows, skipped = loader.load_insights()
    ni = repo.upsert_insights(insights)
    repo.upsert_insight_clusters(ic_rows)
    repo.upsert_insight_reviews(ir_rows)

    jtbd_rows, _ = loader.load_jtbd()
    repo.upsert_jtbd(jtbd_rows)

    seg_rows, _ = loader.load_segments()
    repo.upsert_segments(seg_rows)

    need_rows, _ = loader.load_unmet_needs()
    repo.upsert_unmet_needs(need_rows)

    run.insight_count = ni
    run.phase5_loaded = True
    logger.info(
        "phase=5 insights=%d jtbd=%d segments=%d needs=%d skipped=%d duration_ms=%d",
        ni, len(jtbd_rows), len(seg_rows), len(need_rows), skipped,
        int((time.time() - t0) * 1000),
    )


# ---------------------------------------------------------------------------
# Vector store population
# ---------------------------------------------------------------------------

def build_vector_store(cfg: StorageConfig, db: DatabaseManager) -> ChromaManager:
    t0 = time.time()
    chroma = ChromaManager(
        persist_dir=cfg.chroma_persist_dir,
        embedding_model=cfg.embedding_model,
        batch_size=cfg.embedding_batch_size,
    )
    chroma.connect()

    # Reviews — only non-duplicate, quality-filtered analyzed reviews
    logger.info("Embedding reviews...")
    rows = db.conn.execute(
        """SELECT a.id, n.clean_text, n.platform,
                  a.sentiment, a.sentiment_score,
                  a.discovery_friction_detected,
                  a.user_segment_signal,
                  n.quality_score, n.language
           FROM analyzed_reviews a
           JOIN normalized_reviews n ON a.normalized_review_id = n.id
           WHERE n.is_duplicate = 0
             AND n.quality_score >= 0.3
             AND a.analysis_status = 'success'"""
    ).fetchall()
    review_rows = [dict(r) for r in rows]
    nr = chroma.upsert_reviews(review_rows)
    logger.info("Embedded %d reviews", nr)

    # Insights
    logger.info("Embedding insights...")
    irows = db.conn.execute("SELECT * FROM insights WHERE review_required = 0").fetchall()
    insight_rows = [dict(r) for r in irows]
    ni = chroma.upsert_insights(insight_rows)
    logger.info("Embedded %d insights", ni)

    # Verbatims — from insight supporting_verbatims
    logger.info("Embedding verbatims...")
    vrows = db.conn.execute(
        "SELECT id, supporting_verbatims FROM insights WHERE supporting_verbatims IS NOT NULL AND supporting_verbatims != '[]'"
    ).fetchall()
    nv = 0
    for row in vrows:
        try:
            verbatims = json.loads(row["supporting_verbatims"])
            if verbatims:
                nv += chroma.upsert_verbatims(row["id"], verbatims)
        except (json.JSONDecodeError, TypeError):
            pass
    logger.info("Embedded %d verbatims", nv)

    elapsed = int((time.time() - t0) * 1000)
    counts = chroma.collection_counts()
    logger.info("Vector store complete: %s duration_ms=%d", counts, elapsed)
    return chroma


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Phase 6 — Storage & Knowledge Base")
    p.add_argument("--db-path", default=None, help="Override DB path")
    p.add_argument("--chroma-dir", default=None, help="Override ChromaDB directory")
    p.add_argument("--skip-vectors", action="store_true", help="Skip vector store population")
    p.add_argument("--only-phase", type=int, choices=[1, 2, 3, 4, 5], default=None,
                   help="Reload only one phase (DB load, skip vectors)")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    cfg = StorageConfig.from_env()
    if args.db_path:
        cfg.db_path = args.db_path
    if args.chroma_dir:
        cfg.chroma_persist_dir = args.chroma_dir

    run = PipelineRun()
    t_start = time.time()
    logger.info("Pipeline run started id=%s db=%s", run.id, cfg.db_path)

    only = args.only_phase

    with DatabaseManager(cfg.db_path) as db:
        save_pipeline_run(db.conn, run.to_db_dict())

        try:
            load_phase1(cfg, db, run, only)
        except Exception as exc:
            msg = f"phase=1 error={exc}"
            logger.error(msg)
            run.add_error(msg)

        try:
            load_phase2(cfg, db, run, only)
        except Exception as exc:
            msg = f"phase=2 error={exc}"
            logger.error(msg)
            run.add_error(msg)

        try:
            load_phase3(cfg, db, run, only)
        except Exception as exc:
            msg = f"phase=3 error={exc}"
            logger.error(msg)
            run.add_error(msg)

        try:
            load_phase4(cfg, db, run, only)
        except Exception as exc:
            msg = f"phase=4 error={exc}"
            logger.error(msg)
            run.add_error(msg)

        try:
            load_phase5(cfg, db, run, only)
        except Exception as exc:
            msg = f"phase=5 error={exc}"
            logger.error(msg)
            run.add_error(msg)

        # Build lineage
        try:
            lb = LineageBuilder(db.conn)
            lb.build()
        except Exception as exc:
            msg = f"lineage error={exc}"
            logger.error(msg)
            run.add_error(msg)

        phases_done = sum([
            run.phase1_loaded, run.phase2_loaded, run.phase3_loaded,
            run.phase4_loaded, run.phase5_loaded,
        ])
        if run.error_log:
            run.finish("partial" if phases_done > 0 else "failed")
        else:
            run.finish("completed")

        save_pipeline_run(db.conn, run.to_db_dict())

    # Vector store (outside DB transaction — ChromaDB manages its own persistence)
    if not args.skip_vectors and only is None:
        try:
            with DatabaseManager(cfg.db_path) as db:
                build_vector_store(cfg, db)
        except Exception as exc:
            logger.error("Vector store failed: %s", exc)

    elapsed = int((time.time() - t_start) * 1000)
    logger.info(
        "Phase 6 %s: raw=%d norm=%d analyzed=%d clusters=%d insights=%d duration_ms=%d errors=%d",
        run.status,
        run.raw_review_count, run.normalized_review_count, run.analyzed_review_count,
        run.cluster_count, run.insight_count,
        elapsed, len(run.error_log),
    )

    # Write quality report
    report = {
        "run_id": run.id,
        "status": run.status,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "duration_ms": elapsed,
        "counts": {
            "raw_reviews": run.raw_review_count,
            "normalized_reviews": run.normalized_review_count,
            "analyzed_reviews": run.analyzed_review_count,
            "clusters": run.cluster_count,
            "insights": run.insight_count,
        },
        "phases_loaded": {
            "phase1": run.phase1_loaded,
            "phase2": run.phase2_loaded,
            "phase3": run.phase3_loaded,
            "phase4": run.phase4_loaded,
            "phase5": run.phase5_loaded,
        },
        "errors": run.error_log,
    }
    report_path = Path("data") / f"quality_report_{run.id[:8]}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("Quality report written to %s", report_path)

    if run.status == "failed":
        sys.exit(1)


if __name__ == "__main__":
    main()
