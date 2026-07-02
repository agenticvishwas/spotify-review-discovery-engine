from __future__ import annotations
import sqlite3
import logging
from typing import Any

logger = logging.getLogger(__name__)

_CHUNK = 500  # rows per executemany batch


def upsert_batch(
    conn: sqlite3.Connection,
    table: str,
    rows: list[dict],
    conflict: str = "REPLACE",
) -> int:
    """Batch upsert rows into table. Returns count inserted."""
    if not rows:
        return 0
    cols = list(rows[0].keys())
    placeholders = ", ".join("?" * len(cols))
    col_list = ", ".join(cols)
    sql = f"INSERT OR {conflict} INTO {table} ({col_list}) VALUES ({placeholders})"

    total = 0
    for i in range(0, len(rows), _CHUNK):
        chunk = rows[i: i + _CHUNK]
        values = [tuple(r[c] for c in cols) for r in chunk]
        conn.executemany(sql, values)
        total += len(chunk)
    conn.commit()
    return total


def save_pipeline_run(conn: sqlite3.Connection, run_dict: dict) -> None:
    upsert_batch(conn, "pipeline_runs", [run_dict])
