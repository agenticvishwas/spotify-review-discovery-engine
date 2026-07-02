"""Phase 1 — Quality Report Viewer.

Standalone utility for inspecting ingestion quality reports produced by the
pipeline. Does not modify any data — read-only.

Usage:
    python quality_report.py                          # list all reports
    python quality_report.py <batch_id>               # show specific report
    python quality_report.py --latest                 # show most recent report
    python quality_report.py --summary               # one-line per report
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional


DEFAULT_DATA_DIR = "data"
REPORTS_DIR_NAME = "quality_reports"


def load_report(batch_id: str, data_dir: str = DEFAULT_DATA_DIR) -> Optional[dict]:
    path = _report_path(batch_id, data_dir)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def list_reports(data_dir: str = DEFAULT_DATA_DIR) -> list[Path]:
    reports_dir = Path(data_dir) / REPORTS_DIR_NAME
    if not reports_dir.exists():
        return []
    return sorted(reports_dir.glob("phase1_*.json"), reverse=True)


def print_report(report: dict) -> None:
    platforms = report.get("platforms", {})
    total_fetched = report.get("total_fetched", 0)
    total_valid = report.get("total_valid", 0)
    total_rejected = report.get("total_rejected", 0)
    error_rate = report.get("error_rate", 0.0)
    dry_run = report.get("dry_run", False)

    print()
    print("=" * 60)
    print("  Phase 1 — Ingestion Quality Report")
    print("=" * 60)
    if dry_run:
        print("  ⚠  DRY RUN — no data was written to disk")
    print(f"  Batch:     {report.get('batch_id', 'n/a')}")
    print(f"  Run date:  {report.get('run_date', 'n/a')}")
    print(f"  Duration:  {report.get('duration_seconds', 0):.1f}s")
    print()
    print(f"  Totals:")
    print(f"    Fetched:   {total_fetched}")
    print(f"    Valid:     {total_valid}")
    print(f"    Rejected:  {total_rejected}")
    print(f"    Error rate: {error_rate * 100:.1f}%", _halt_flag(error_rate))
    print()
    print("  By Platform:")
    for platform, stats in platforms.items():
        print(f"    {platform}:")
        print(f"      fetched={stats['fetched']}  valid={stats['valid']}  rejected={stats['rejected']}")
        reasons = stats.get("rejection_reasons", {})
        for reason, count in reasons.items():
            print(f"        - {reason}: {count}")
    print("=" * 60)
    print()


def print_summary_line(path: Path) -> None:
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
        batch_id = report.get("batch_id", "?")[:8]
        run_date = report.get("run_date", "?")[:10]
        fetched = report.get("total_fetched", 0)
        valid = report.get("total_valid", 0)
        error_rate = report.get("error_rate", 0.0)
        flag = _halt_flag(error_rate)
        print(f"  {run_date}  {batch_id}...  fetched={fetched}  valid={valid}  err={error_rate*100:.1f}% {flag}")
    except Exception:
        print(f"  [unreadable] {path.name}")


def _report_path(batch_id: str, data_dir: str) -> Path:
    return Path(data_dir) / REPORTS_DIR_NAME / f"phase1_{batch_id}.json"


def _halt_flag(error_rate: float) -> str:
    return "⚠ ABOVE HALT THRESHOLD" if error_rate > 0.05 else ""


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 1 Quality Report Viewer")
    parser.add_argument("batch_id", nargs="?", help="Batch ID to display")
    parser.add_argument("--latest", action="store_true", help="Show the most recent report")
    parser.add_argument("--summary", action="store_true", help="One-line summary per report")
    parser.add_argument("--data-dir", default=DEFAULT_DATA_DIR)
    args = parser.parse_args()

    if args.batch_id:
        report = load_report(args.batch_id, args.data_dir)
        if not report:
            print(f"Report not found for batch: {args.batch_id}", file=sys.stderr)
            return 1
        print_report(report)
        return 0

    reports = list_reports(args.data_dir)
    if not reports:
        print("No Phase 1 quality reports found. Run the ingestion pipeline first.")
        return 0

    if args.latest:
        report = json.loads(reports[0].read_text(encoding="utf-8"))
        print_report(report)
        return 0

    if args.summary:
        print(f"\nPhase 1 Quality Reports ({len(reports)} found):\n")
        for path in reports:
            print_summary_line(path)
        print()
        return 0

    # Default: list available report filenames
    print(f"\nPhase 1 Quality Reports ({len(reports)} found):\n")
    for path in reports:
        batch_id = path.stem.replace("phase1_", "")
        print(f"  {batch_id}  →  python quality_report.py {batch_id}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
