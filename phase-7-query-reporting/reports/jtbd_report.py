"""JTBD Report generator.

Produces a Markdown table + gap chart data from jtbd_profiles in the knowledge base.
"""
from __future__ import annotations
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def generate_markdown(
    conn: sqlite3.Connection,
    output_path: Optional[Path] = None,
) -> str:
    conn.row_factory = sqlite3.Row
    profiles = [
        dict(r)
        for r in conn.execute(
            "SELECT * FROM jtbd_profiles ORDER BY gap_score DESC"
        ).fetchall()
    ]

    lines = [
        "# Jobs-to-Be-Done Report",
        "",
        f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"**Total JTBD profiles:** {len(profiles)}",
        "",
        "---",
        "",
        "| # | Job Statement | Satisfaction | Gap Score | Est. Reviews | Segments |",
        "|---|---|---|---|---|---|",
    ]

    for i, p in enumerate(profiles, 1):
        sat = f"{p.get('satisfaction_score', 0):.2f}" if p.get("satisfaction_score") is not None else "—"
        gap = f"{p.get('gap_score', 0):.2f}" if p.get("gap_score") is not None else "—"
        lines.append(
            f"| {i} | {p.get('job_statement', '')} | {sat} | {gap} "
            f"| {p.get('frequency_estimate', '—')} | {p.get('user_segments', '—')} |"
        )

    lines += ["", "---", ""]

    if profiles:
        top = profiles[0]
        lines += [
            "## Highest-Gap Job",
            "",
            f"**{top.get('short_label', '')}**",
            "",
            f"> {top.get('job_statement', '')}",
            "",
            f"Gap Score: **{top.get('gap_score', 0):.2f}** | "
            f"Satisfaction: **{top.get('satisfaction_score', 0):.2f}**",
            "",
            f"{top.get('gap_description', '')}",
            "",
        ]

    output = "\n".join(lines)
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output, encoding="utf-8")
    return output


def generate_json(
    conn: sqlite3.Connection,
    output_path: Optional[Path] = None,
) -> str:
    conn.row_factory = sqlite3.Row
    profiles = [
        dict(r)
        for r in conn.execute(
            "SELECT * FROM jtbd_profiles ORDER BY gap_score DESC"
        ).fetchall()
    ]
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(profiles),
        "jtbd_profiles": profiles,
    }
    output = json.dumps(report, indent=2, default=str)
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output, encoding="utf-8")
    return output
