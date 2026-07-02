import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union

from models.raw_review import RawReview

logger = logging.getLogger(__name__)

DEFAULT_RAW_DIR = Path("data") / "raw_reviews"


class RawStore:
    """Append-only JSONL writer and reader for Phase 1 raw review output.

    Storage layout (immutable after write):
        {base_dir}/{platform}/{YYYY-MM-DD}/{batch_id}.jsonl

    Downstream phases read from this layout; they must never write to it.
    """

    def __init__(self, base_dir: Union[str, Path] = DEFAULT_RAW_DIR):
        self._base_dir = Path(base_dir)

    # ── Write ────────────────────────────────────────────────────────────────

    def write(self, reviews: list[RawReview], batch_id: str) -> Path:
        """Append reviews to their platform-partitioned JSONL file.

        Each call is atomic per review line; partial batches are still
        recoverable — Phase 2 deduplication handles any overlap on retry.
        Returns the output path.
        """
        if not reviews:
            return Path()

        platform = reviews[0].source_platform
        out_path = self._batch_path(platform, batch_id)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        written = 0
        with out_path.open("a", encoding="utf-8") as fh:
            for review in reviews:
                fh.write(review.to_jsonl() + "\n")
                written += 1

        logger.info(
            "phase=1 action=write platform=%s batch=%s records=%d path=%s",
            platform, batch_id, written, out_path,
        )
        return out_path

    def write_error_log(
        self,
        rejected: list[dict],
        batch_id: str,
        platform: str,
    ) -> Path:
        """Persist rejected records with their rejection reasons.

        Rejected records are never deleted — this log provides full auditability.
        """
        err_path = self._error_path(platform, batch_id)
        err_path.parent.mkdir(parents=True, exist_ok=True)

        with err_path.open("a", encoding="utf-8") as fh:
            for record in rejected:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")

        logger.info(
            "phase=1 action=write_errors platform=%s batch=%s records=%d path=%s",
            platform, batch_id, len(rejected), err_path,
        )
        return err_path

    def write_batch_manifest(self, batch_data: dict, batch_id: str, platform: str) -> Path:
        """Write an IngestionBatch summary alongside its JSONL file."""
        manifest_path = self._manifest_path(platform, batch_id)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with manifest_path.open("w", encoding="utf-8") as fh:
            json.dump(batch_data, fh, indent=2, ensure_ascii=False)
        return manifest_path

    # ── Read ─────────────────────────────────────────────────────────────────

    def read_batch(self, platform: str, batch_id: str, date_str: Optional[str] = None) -> list[RawReview]:
        """Read all valid reviews from a specific batch file."""
        path = self._batch_path(platform, batch_id, date_str)
        if not path.exists():
            logger.warning("Batch file not found: %s", path)
            return []

        reviews: list[RawReview] = []
        with path.open("r", encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    reviews.append(RawReview.model_validate_json(line))
                except Exception as exc:
                    logger.warning("Skipping malformed JSONL at %s:%d — %s", path, lineno, exc)

        return reviews

    def list_batches(self, platform: str, date_str: str) -> list[Path]:
        """List all batch JSONL files for a given platform + date."""
        dir_path = self._base_dir / platform / date_str
        if not dir_path.exists():
            return []
        return sorted(p for p in dir_path.glob("*.jsonl") if not p.name.endswith(".errors.jsonl"))

    # ── Path helpers ─────────────────────────────────────────────────────────

    def _today(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _batch_path(self, platform: str, batch_id: str, date_str: Optional[str] = None) -> Path:
        return self._base_dir / platform / (date_str or self._today()) / f"{batch_id}.jsonl"

    def _error_path(self, platform: str, batch_id: str, date_str: Optional[str] = None) -> Path:
        return self._base_dir / platform / (date_str or self._today()) / f"{batch_id}.errors.jsonl"

    def _manifest_path(self, platform: str, batch_id: str, date_str: Optional[str] = None) -> Path:
        return self._base_dir / platform / (date_str or self._today()) / f"{batch_id}.manifest.json"
