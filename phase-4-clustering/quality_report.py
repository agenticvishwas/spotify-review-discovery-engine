"""Phase 4 quality report reader and formatter.

Reads quality reports produced by clustering_pipeline.py and prints a human-readable
summary. Useful for auditing a run without loading the full JSONL.

Usage:
    python quality_report.py
    python quality_report.py --data-dir data
    python quality_report.py --batch-id <uuid>
"""

import argparse
import json
import sys
from pathlib import Path


def load_latest_report(data_dir: Path) -> dict | None:
    reports_dir = data_dir / "quality_reports"
    if not reports_dir.exists():
        return None
    paths = sorted(reports_dir.glob("phase4_*.json"), key=lambda p: p.stat().st_mtime)
    if not paths:
        return None
    return json.loads(paths[-1].read_text(encoding="utf-8"))


def load_report_by_batch(data_dir: Path, batch_id: str) -> dict | None:
    path = data_dir / "quality_reports" / f"phase4_{batch_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def format_report(report: dict) -> str:
    lines = [
        "=" * 60,
        "PHASE 4 — CLUSTERING QUALITY REPORT",
        "=" * 60,
        f"Batch ID     : {report.get('batch_id', 'n/a')}",
        f"Date         : {report.get('target_date', 'n/a')}",
        f"Run At       : {report.get('run_date', 'n/a')}",
        f"Duration     : {report.get('duration_seconds', 0):.1f}s",
        f"Dry Run      : {report.get('dry_run', False)}",
        f"Provider     : {report.get('labeling_provider', 'n/a')}",
        f"Model        : {report.get('labeling_model', 'n/a')}",
        f"Batch Size   : {report.get('label_batch_size', 'n/a')} clusters/call",
        f"Concurrency  : {report.get('label_concurrency', 'n/a')} parallel batches",
        "",
    ]

    totals = report.get("totals", {})
    if totals:
        lines += [
            "── Cluster Totals ──────────────────────────────────",
            f"  Reviews input         : {totals.get('reviews_input', 'n/a')}",
            f"  Total clusters        : {totals.get('total_clusters', 'n/a')}",
            f"  Micro-clusters (< 5)  : {totals.get('micro_clusters', 'n/a')}",
            f"  Noise before fallback : {totals.get('noise_points_before_fallback', 'n/a')}",
            f"  Noise rate            : {totals.get('noise_rate', 0):.1%}",
            f"  Avg cluster size      : {totals.get('avg_cluster_size', 'n/a')}",
            f"  Largest cluster       : {totals.get('largest_cluster_size', 'n/a')} reviews",
            "",
        ]

    labeling = report.get("labeling_quality", {})
    if labeling:
        lines += [
            "── Labeling Quality ────────────────────────────────",
            f"  Avg confidence        : {labeling.get('avg_confidence', 0):.2f}",
            f"  Below threshold       : {labeling.get('below_threshold', 'n/a')} clusters",
            f"  Threshold             : {labeling.get('confidence_threshold', 'n/a')}",
            "",
        ]

    signals = report.get("cluster_signals", {})
    if signals:
        lines += [
            "── Cluster Signals ─────────────────────────────────",
            f"  Discovery-related     : {signals.get('discovery_related_clusters', 'n/a')} clusters",
            f"  Discovery rate        : {signals.get('discovery_cluster_rate', 0):.1%}",
        ]
        trend_dist = signals.get("trend_distribution", {})
        if trend_dist:
            lines.append(f"  Trend distribution    : {trend_dist}")
        lines.append("")

    note = report.get("note")
    if note:
        lines += [f"NOTE: {note}", ""]

    lines.append("=" * 60)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 4 Quality Report Viewer")
    parser.add_argument("--data-dir", default="data", help="Root data directory")
    parser.add_argument("--batch-id", default=None, help="Specific batch ID to load")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    report = (
        load_report_by_batch(data_dir, args.batch_id)
        if args.batch_id
        else load_latest_report(data_dir)
    )

    if report is None:
        print("No Phase 4 quality reports found.", file=sys.stderr)
        return 1

    print(format_report(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
