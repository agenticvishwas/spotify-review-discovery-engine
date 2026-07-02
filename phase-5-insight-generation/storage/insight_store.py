"""Append-only JSONL storage for Phase 5 insight outputs.

Storage layout (mirrors Phase 3/4 patterns):
  data/insights/{YYYY-MM-DD}/
    product_insights_{batch_id}.jsonl
    jtbd_profiles_{batch_id}.jsonl
    user_segments_{batch_id}.jsonl
    unmet_needs_{batch_id}.jsonl
  data/quality_reports/
    phase5_{batch_id}.json
"""

import json
import logging
from pathlib import Path
from typing import Union

from schemas.product_insight import JTBDProfile, ProductInsight, UnmetNeed, UserSegment

logger = logging.getLogger(__name__)

_DEFAULT_BASE_DIR = Path(__file__).parent.parent / "data" / "insights"
_DEFAULT_REPORT_DIR = Path(__file__).parent.parent / "data" / "quality_reports"


class InsightStore:
    """Read/write for all Phase 5 output types."""

    def __init__(
        self,
        base_dir: Union[str, Path] = _DEFAULT_BASE_DIR,
        report_dir: Union[str, Path] = _DEFAULT_REPORT_DIR,
    ):
        self._base_dir = Path(base_dir)
        self._report_dir = Path(report_dir)

    # ── Write ────────────────────────────────────────────────────────────────

    def write_product_insights(
        self,
        insights: list[ProductInsight],
        batch_id: str,
        date_str: str,
    ) -> Path:
        return self._write_jsonl(
            [i.to_jsonl() for i in insights],
            date_str, f"product_insights_{batch_id}.jsonl",
        )

    def write_jtbd_profiles(
        self,
        profiles: list[JTBDProfile],
        batch_id: str,
        date_str: str,
    ) -> Path:
        return self._write_jsonl(
            [p.to_jsonl() for p in profiles],
            date_str, f"jtbd_profiles_{batch_id}.jsonl",
        )

    def write_user_segments(
        self,
        segments: list[UserSegment],
        batch_id: str,
        date_str: str,
    ) -> Path:
        return self._write_jsonl(
            [s.to_jsonl() for s in segments],
            date_str, f"user_segments_{batch_id}.jsonl",
        )

    def write_unmet_needs(
        self,
        needs: list[UnmetNeed],
        batch_id: str,
        date_str: str,
    ) -> Path:
        return self._write_jsonl(
            [n.to_jsonl() for n in needs],
            date_str, f"unmet_needs_{batch_id}.jsonl",
        )

    def write_quality_report(self, report: dict, batch_id: str) -> Path:
        self._report_dir.mkdir(parents=True, exist_ok=True)
        path = self._report_dir / f"phase5_{batch_id}.json"
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("store=quality_report path=%s", path)
        return path

    # ── Read ─────────────────────────────────────────────────────────────────

    def list_product_insights(self, date_str: str) -> list[ProductInsight]:
        return [
            ProductInsight.model_validate_json(line)
            for line in self._iter_lines(date_str, "product_insights_*.jsonl")
        ]

    def list_jtbd_profiles(self, date_str: str) -> list[JTBDProfile]:
        return [
            JTBDProfile.model_validate_json(line)
            for line in self._iter_lines(date_str, "jtbd_profiles_*.jsonl")
        ]

    def list_user_segments(self, date_str: str) -> list[UserSegment]:
        return [
            UserSegment.model_validate_json(line)
            for line in self._iter_lines(date_str, "user_segments_*.jsonl")
        ]

    def list_unmet_needs(self, date_str: str) -> list[UnmetNeed]:
        return [
            UnmetNeed.model_validate_json(line)
            for line in self._iter_lines(date_str, "unmet_needs_*.jsonl")
        ]

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _write_jsonl(self, lines: list[str], date_str: str, filename: str) -> Path:
        date_dir = self._base_dir / date_str
        date_dir.mkdir(parents=True, exist_ok=True)
        path = date_dir / filename
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        logger.info("store=write path=%s records=%d", path, len(lines))
        return path

    def _iter_lines(self, date_str: str, glob_pattern: str):
        date_dir = self._base_dir / date_str
        if not date_dir.exists():
            return
        for path in sorted(date_dir.glob(glob_pattern)):
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    yield line
