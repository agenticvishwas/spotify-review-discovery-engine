import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union

from models.normalized_review import NormalizedReview

logger = logging.getLogger(__name__)

DEFAULT_NORMALIZED_DIR = Path("data") / "normalized_reviews"


class NormalizedStore:
    """Append-only JSONL writer and reader for Phase 2 normalized review output.

    Storage layout:
        {base_dir}/{platform}/{YYYY-MM-DD}/{batch_id}.jsonl

    Excluded records (non-English, duplicates, low-quality) are written to a
    separate audit log — never deleted, always inspectable.
    """

    def __init__(self, base_dir: Union[str, Path] = DEFAULT_NORMALIZED_DIR):
        self._base_dir = Path(base_dir)

    # ── Write ────────────────────────────────────────────────────────────────

    def write(self, reviews: list[NormalizedReview], batch_id: str) -> list[Path]:
        """Write reviews partitioned by platform. Returns list of written paths."""
        if not reviews:
            return []

        by_platform: dict[str, list[NormalizedReview]] = {}
        for r in reviews:
            by_platform.setdefault(r.platform, []).append(r)

        paths: list[Path] = []
        for platform, platform_reviews in by_platform.items():
            out_path = self._batch_path(platform, batch_id)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with out_path.open("a", encoding="utf-8") as fh:
                for review in platform_reviews:
                    fh.write(review.to_jsonl() + "\n")
            logger.info(
                "phase=2 action=write platform=%s batch=%s records=%d path=%s",
                platform, batch_id, len(platform_reviews), out_path,
            )
            paths.append(out_path)
        return paths

    def write_excluded(self, excluded: list[dict], batch_id: str) -> Path:
        """Persist excluded records with their exclusion reason for audit."""
        out_path = self._excluded_path(batch_id)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("a", encoding="utf-8") as fh:
            for record in excluded:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        logger.info(
            "phase=2 action=write_excluded batch=%s records=%d path=%s",
            batch_id, len(excluded), out_path,
        )
        return out_path

    def write_batch_manifest(self, batch_data: dict, batch_id: str) -> Path:
        manifest_path = self._manifest_path(batch_id)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with manifest_path.open("w", encoding="utf-8") as fh:
            json.dump(batch_data, fh, indent=2, ensure_ascii=False)
        return manifest_path

    # ── Read ─────────────────────────────────────────────────────────────────

    def read_batch(self, platform: str, batch_id: str, date_str: Optional[str] = None) -> list[NormalizedReview]:
        path = self._batch_path(platform, batch_id, date_str)
        if not path.exists():
            logger.warning("Normalized batch file not found: %s", path)
            return []
        return self._read_jsonl(path)

    def list_all_reviews(self, date_str: Optional[str] = None) -> list[NormalizedReview]:
        """Read all normalized reviews across all platforms for a given date."""
        today = date_str or self._today()
        reviews: list[NormalizedReview] = []
        if not self._base_dir.exists():
            return reviews
        for platform_dir in sorted(self._base_dir.iterdir()):
            if not platform_dir.is_dir() or platform_dir.name in ("excluded", "manifests"):
                continue
            date_dir = platform_dir / today
            if not date_dir.exists():
                continue
            for jsonl_path in sorted(date_dir.glob("*.jsonl")):
                reviews.extend(self._read_jsonl(jsonl_path))
        return reviews

    def _read_jsonl(self, path: Path) -> list[NormalizedReview]:
        reviews: list[NormalizedReview] = []
        with path.open("r", encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    reviews.append(NormalizedReview.model_validate_json(line))
                except Exception as exc:
                    logger.warning("Skipping malformed JSONL at %s:%d — %s", path, lineno, exc)
        return reviews

    # ── Path helpers ─────────────────────────────────────────────────────────

    def _today(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _batch_path(self, platform: str, batch_id: str, date_str: Optional[str] = None) -> Path:
        return self._base_dir / platform / (date_str or self._today()) / f"{batch_id}.jsonl"

    def _excluded_path(self, batch_id: str, date_str: Optional[str] = None) -> Path:
        return self._base_dir / "excluded" / (date_str or self._today()) / f"{batch_id}.excluded.jsonl"

    def _manifest_path(self, batch_id: str, date_str: Optional[str] = None) -> Path:
        return self._base_dir / "manifests" / (date_str or self._today()) / f"{batch_id}.manifest.json"
