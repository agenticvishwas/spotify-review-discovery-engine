"""Phase 2 — Quality Report Viewer.

Standalone utility for inspecting preprocessing quality reports. Read-only.

Usage:
    python quality_report.py                    # list all reports
    python quality_report.py <batch_id>         # show specific report
    python quality_report.py --latest           # show most recent report
    python quality_report.py --summary          # one-line per report
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
    return sorted(reports_dir.glob("phase2_*.json"), reverse=True)


def print_report(report: dict) -> None:
    stages = report.get("stages", {})
    quality = report.get("output_quality", {})
    dry_run = report.get("dry_run", False)

    html_mod = stages.get("html_cleaning", {}).get("modified", 0)
    lang_excl = stages.get("language_filter", {}).get("excluded", 0)
    lang_breakdown = stages.get("language_filter", {}).get("language_breakdown", {})
    exact_rem = stages.get("exact_dedup", {}).get("removed", 0)
    near_rem = stages.get("near_dup", {}).get("removed", 0)
    qual_excl = stages.get("quality_filter", {}).get("excluded", 0)
    avg_qual = stages.get("quality_filter", {}).get("avg_quality_score", 0.0)

    print()
    print("=" * 60)
    print("  Phase 2 — Preprocessing Quality Report")
    print("=" * 60)
    if dry_run:
        print("  ⚠  DRY RUN — no data was written to disk")
    print(f"  Batch:     {report.get('batch_id', 'n/a')}")
    print(f"  Run date:  {report.get('run_date', 'n/a')}")
    print(f"  Duration:  {report.get('duration_seconds', 0):.1f}s")
    print()
    print(f"  Totals:")
    print(f"    Input:   {report.get('total_input', 0)}")
    print(f"    Output:  {report.get('total_output', 0)}")
    note = report.get("note")
    if note:
        print(f"    Note:    {note}")
        print("=" * 60)
        print()
        return
    print()
    print(f"  Stage breakdown:")
    print(f"    HTML cleaned:        {html_mod} modified")
    print(f"    Language filtered:   {lang_excl} excluded")
    if lang_breakdown:
        for lang, count in sorted(lang_breakdown.items(), key=lambda x: -x[1]):
            print(f"      {lang}: {count}")
    print(f"    Exact duplicates:    {exact_rem} removed")
    print(f"    Near duplicates:     {near_rem} removed")
    print(f"    Low quality:         {qual_excl} excluded (threshold={report.get('output_quality', {}).get('quality_threshold', 0.3)})")
    print(f"    Avg quality score:   {avg_qual:.3f}")
    print()
    print(f"  Output quality:")
    print(f"    Avg word count:      {quality.get('avg_word_count', 0):.1f}")
    print(f"    Avg quality score:   {quality.get('avg_quality_score', 0):.3f}")
    print(f"    Rating coverage:     {quality.get('rating_coverage', 0) * 100:.1f}%")
    print(f"    Passes threshold:    {quality.get('passing_quality_threshold', 0)}")
    print("=" * 60)
    print()


def print_summary_line(path: Path) -> None:
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
        batch_id = report.get("batch_id", "?")[:8]
        run_date = report.get("run_date", "?")[:10]
        total_in = report.get("total_input", 0)
        total_out = report.get("total_output", 0)
        retention = (total_out / total_in * 100) if total_in else 0.0
        avg_q = report.get("output_quality", {}).get("avg_quality_score", 0.0)
        print(f"  {run_date}  {batch_id}...  input={total_in}  output={total_out}  kept={retention:.1f}%  avg_q={avg_q:.3f}")
    except Exception:
        print(f"  [unreadable] {path.name}")


def _report_path(batch_id: str, data_dir: str) -> Path:
    return Path(data_dir) / REPORTS_DIR_NAME / f"phase2_{batch_id}.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 2 Quality Report Viewer")
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
        print("No Phase 2 quality reports found. Run the preprocessing pipeline first.")
        return 0

    if args.latest:
        report = json.loads(reports[0].read_text(encoding="utf-8"))
        print_report(report)
        return 0

    if args.summary:
        print(f"\nPhase 2 Quality Reports ({len(reports)} found):\n")
        for path in reports:
            print_summary_line(path)
        print()
        return 0

    print(f"\nPhase 2 Quality Reports ({len(reports)} found):\n")
    for path in reports:
        batch_id = path.stem.replace("phase2_", "")
        print(f"  {batch_id}  →  python quality_report.py {batch_id}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
