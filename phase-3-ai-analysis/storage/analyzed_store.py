"""Append-only JSONL writer/reader for Phase 3 AnalyzedReview output.

Storage layout:
    {base_dir}/{YYYY-MM-DD}/{batch_id}.jsonl          — successful analyses
    {base_dir}/{YYYY-MM-DD}/{batch_id}.failed.jsonl   — failed analyses
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union

from schemas.analyzed_review import AnalyzedReview

logger = logging.getLogger(__name__)

DEFAULT_ANALYZED_DIR = Path("data") / "analyzed_reviews"


class AnalyzedStore:
    def __init__(self, base_dir: Union[str, Path] = DEFAULT_ANALYZED_DIR):
        self._base_dir = Path(base_dir)

    # ── Write ────────────────────────────────────────────────────────────────

    def append(self, review: AnalyzedReview, batch_id: str, date_str: Optional[str] = None) -> None:
        """Append a single AnalyzedReview to the batch JSONL file."""
        if review.analysis_status == "failed":
            path = self._failed_path(batch_id, date_str)
        else:
            path = self._batch_path(batch_id, date_str)

        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(review.to_jsonl() + "\n")

    def write_batch(
        self,
        reviews: list[AnalyzedReview],
        batch_id: str,
        date_str: Optional[str] = None,
    ) -> dict[str, Path]:
        """Write all reviews at once, returning paths written."""
        successes = [r for r in reviews if r.analysis_status != "failed"]
        failures = [r for r in reviews if r.analysis_status == "failed"]
        paths: dict[str, Path] = {}

        if successes:
            path = self._batch_path(batch_id, date_str)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                for r in successes:
                    fh.write(r.to_jsonl() + "\n")
            logger.info(
                "phase=3 action=write batch=%s records=%d path=%s",
                batch_id, len(successes), path,
            )
            paths["success"] = path

        if failures:
            path = self._failed_path(batch_id, date_str)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                for r in failures:
                    fh.write(r.to_jsonl() + "\n")
            logger.info(
                "phase=3 action=write_failed batch=%s records=%d path=%s",
                batch_id, len(failures), path,
            )
            paths["failed"] = path

        return paths

    # ── Read ─────────────────────────────────────────────────────────────────

    def load_analyzed_ids(self, date_str: Optional[str] = None) -> set[str]:
        """Return the set of normalized_review_ids already written for a date."""
        ids: set[str] = set()
        today = date_str or self._today()
        date_dir = self._base_dir / today
        if not date_dir.exists():
            return ids
        for path in date_dir.glob("*.jsonl"):
            if path.name.endswith(".failed.jsonl"):
                continue
            for review in self._read_jsonl(path):
                ids.add(review.normalized_review_id)
        return ids

    def list_all(self, date_str: Optional[str] = None) -> list[AnalyzedReview]:
        """Read all analyzed reviews for a given date."""
        today = date_str or self._today()
        reviews: list[AnalyzedReview] = []
        date_dir = self._base_dir / today
        if not date_dir.exists():
            return reviews
        for path in sorted(date_dir.glob("*.jsonl")):
            if path.name.endswith(".failed.jsonl"):
                continue
            reviews.extend(self._read_jsonl(path))
        return reviews

    def _read_jsonl(self, path: Path) -> list[AnalyzedReview]:
        reviews: list[AnalyzedReview] = []
        with path.open("r", encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    reviews.append(AnalyzedReview.model_validate_json(line))
                except Exception as exc:
                    logger.warning(
                        "Skipping malformed JSONL at %s:%d — %s", path, lineno, exc
                    )
        return reviews

    # ── Path helpers ─────────────────────────────────────────────────────────

    def _today(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _batch_path(self, batch_id: str, date_str: Optional[str] = None) -> Path:
        return self._base_dir / (date_str or self._today()) / f"{batch_id}.jsonl"

    def _failed_path(self, batch_id: str, date_str: Optional[str] = None) -> Path:
        return self._base_dir / (date_str or self._today()) / f"{batch_id}.failed.jsonl"
