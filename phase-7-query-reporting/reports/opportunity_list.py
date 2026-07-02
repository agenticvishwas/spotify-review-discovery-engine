"""Opportunity List report generator.

Produces a full ranked opportunity list with evidence as JSON or CSV.
Every row includes supporting_review_ids and verbatims for lineage tracing.
"""
from __future__ import annotations
import csv
import io
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def generate_json(
    conn: sqlite3.Connection,
    include_pending: bool = False,
    output_path: Optional[Path] = None,
) -> str:
    """Return JSON string of all opportunities ranked by opportunity_score."""
    conn.row_factory = sqlite3.Row
    sql = "SELECT * FROM insights"
    if not include_pending:
        sql += " WHERE review_required = 0"
    sql += " ORDER BY opportunity_score DESC"

    insights = [dict(r) for r in conn.execute(sql).fetchall()]

    for ins in insights:
        # Attach verbatims
        rows = conn.execute(
            "SELECT verbatim, review_id FROM insight_reviews WHERE insight_id=? AND verbatim IS NOT NULL",
            (ins["id"],),
        ).fetchall()
        ins["supporting_verbatims"] = [r["verbatim"] for r in rows]
        ins["supporting_review_ids"] = [r["review_id"] for r in rows]

        # Attach cluster IDs
        cluster_rows = conn.execute(
            "SELECT cluster_id FROM insight_clusters WHERE insight_id=?", (ins["id"],)
        ).fetchall()
        ins["supporting_cluster_ids"] = [r["cluster_id"] for r in cluster_rows]

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(insights),
        "include_pending": include_pending,
        "opportunities": insights,
    }

    output = json.dumps(report, indent=2, default=str)
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output, encoding="utf-8")
    return output


def generate_csv(
    conn: sqlite3.Connection,
    include_pending: bool = False,
    output_path: Optional[Path] = None,
) -> str:
    """Return CSV string of all opportunities (aggregated columns, no verbatim arrays)."""
    conn.row_factory = sqlite3.Row
    sql = "SELECT * FROM insights"
    if not include_pending:
        sql += " WHERE review_required = 0"
    sql += " ORDER BY opportunity_score DESC"

    insights = [dict(r) for r in conn.execute(sql).fetchall()]

    fieldnames = [
        "title", "insight_type", "affected_segment", "opportunity_score",
        "frequency_score", "severity_score", "confidence", "confidence_score",
        "discovery_friction_related", "trend_direction", "review_required",
        "description", "generated_at",
    ]

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(insights)
    output = buf.getvalue()

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output, encoding="utf-8")
    return output
