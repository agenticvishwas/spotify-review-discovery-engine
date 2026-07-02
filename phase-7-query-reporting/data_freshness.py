"""Scopes Phase 7 reads to the most recent Phases 1-6 run.

Phases 4/5 give every row a brand-new ID on each run (clusters genuinely
differ run to run, so there's no content key to dedupe by), and Phase 6's
loader is an append-only upsert keyed on that ID. Re-running the pipeline
without clearing prior data therefore leaves old runs' clusters/insights/
jtbd/segments sitting alongside the latest run's. Rather than deleting that
history, every read here is scoped to rows generated within a few minutes of
the most recent timestamp in the table, which is sufficient to isolate one
run's rows (runs are scheduled minutes-to-hours apart; rows within a single
run land within the same second).
"""
from __future__ import annotations
from datetime import datetime, timedelta
from typing import Optional

_RUN_GAP_TOLERANCE = timedelta(minutes=5)


def latest_run_cutoff(conn, table: str, ts_column: str) -> Optional[str]:
    """ISO timestamp cutoff: rows with ts_column >= this belong to the latest run."""
    row = conn.execute(f"SELECT MAX({ts_column}) FROM {table}").fetchone()
    max_ts = row[0] if row else None
    if not max_ts:
        return None
    return (datetime.fromisoformat(max_ts) - _RUN_GAP_TOLERANCE).isoformat()
