"""Executive Summary report generator.

Produces a Markdown report from the knowledge base: top opportunities, JTBD,
and discovery friction summary. Every opportunity is backed by evidence.
"""
from __future__ import annotations
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader

_TEMPLATE_DIR = Path(__file__).parent / "templates"


def _format_int(value: int) -> str:
    return f"{value:,}"


def generate(
    conn: sqlite3.Connection,
    top_n: int = 5,
    output_path: Optional[Path] = None,
) -> str:
    """Generate the executive summary as a Markdown string.

    Args:
        conn: Open SQLite connection to the knowledge base.
        top_n: Number of top opportunities to include.
        output_path: If provided, also write the report to this file.

    Returns:
        Rendered Markdown string.
    """
    conn.row_factory = sqlite3.Row

    # Top opportunities
    opportunities = [
        dict(r)
        for r in conn.execute(
            "SELECT * FROM insights WHERE review_required=0 ORDER BY opportunity_score DESC LIMIT ?",
            (top_n,),
        ).fetchall()
    ]

    # Attach verbatims to each opportunity
    for opp in opportunities:
        rows = conn.execute(
            "SELECT verbatim FROM insight_reviews WHERE insight_id=? AND verbatim IS NOT NULL LIMIT 3",
            (opp["id"],),
        ).fetchall()
        opp["verbatims"] = [r["verbatim"] for r in rows]

    # JTBD profiles
    jtbd = [
        dict(r)
        for r in conn.execute(
            "SELECT job_statement, satisfaction_score, gap_score FROM jtbd_profiles ORDER BY gap_score DESC LIMIT 10"
        ).fetchall()
    ]

    # Discovery stats
    total_reviews = conn.execute("SELECT COUNT(*) FROM normalized_reviews").fetchone()[0]
    friction_count = conn.execute(
        "SELECT COUNT(*) FROM analyzed_reviews WHERE discovery_friction_detected=1 AND analysis_status='success'"
    ).fetchone()[0]
    friction_rate = round(friction_count / total_reviews * 100, 1) if total_reviews > 0 else 0.0

    # Dates
    row = conn.execute(
        "SELECT MIN(published_at), MAX(published_at) FROM normalized_reviews WHERE published_at IS NOT NULL"
    ).fetchone()
    period_start = (row[0] or "")[:10]
    period_end = (row[1] or "")[:10]

    # Top friction clusters
    top_friction_clusters = [
        dict(r)
        for r in conn.execute(
            """SELECT label, size, discovery_friction_rate
               FROM clusters WHERE is_discovery_related=1 AND is_micro_cluster=0
               ORDER BY discovery_friction_rate DESC LIMIT 5"""
        ).fetchall()
    ]

    env = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)))
    env.filters["format_int"] = _format_int
    template = env.get_template("executive_summary.md.j2")

    rendered = template.render(
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        total_reviews=total_reviews,
        period_start=period_start or "—",
        period_end=period_end or "—",
        friction_rate=friction_rate,
        opportunities=opportunities,
        jtbd=jtbd,
        top_friction_clusters=top_friction_clusters,
    )

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8")

    return rendered
