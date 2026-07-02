"""Phase 2 — Preprocessing Pipeline Orchestrator.

Reads RawReview JSONL files from Phase 1 output, runs all preprocessing stages,
writes NormalizedReview records to JSONL storage, and emits a quality report.

Stages (in order, all deterministic — no AI):
    1. HTML cleaning
    2. Emoji handling
    3. Whitespace normalization
    4. Special character filtering
    5. Language detection (non-English → excluded)
    6. Exact deduplication (SHA-256)
    7. Near-duplicate detection (MinHash)
    8. Rating normalization
    9. Date normalization
    10. Quality scoring

Usage:
    python preprocessing_pipeline.py                        # uses defaults
    python preprocessing_pipeline.py --phase1-dir ../phase-1-data-ingestion/data/raw_reviews
    python preprocessing_pipeline.py --date 2026-06-29     # process a specific date
    python preprocessing_pipeline.py --dry-run             # process but skip writing
"""

import argparse
import json
import logging
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from cleaners.html_cleaner import HTMLCleaner
from cleaners.emoji_handler import EmojiHandler
from cleaners.whitespace_cleaner import WhitespaceCleaner
from cleaners.special_char_filter import SpecialCharFilter
from validators.language_detector import LanguageDetector
from validators.quality_scorer import QualityScorer
from deduplication.exact_deduplicator import ExactDeduplicator
from deduplication.near_dup_detector import NearDupDetector
from normalizers.rating_normalizer import RatingNormalizer
from normalizers.date_normalizer import DateNormalizer
from normalizers.platform_mapper import PlatformMapper
from models.normalized_review import NormalizedReview, QUALITY_THRESHOLD
from models.preprocessing_batch import PreprocessingBatch
from storage.normalized_store import NormalizedStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("phase2.pipeline")

DEFAULT_PHASE1_DIR = Path("..") / "phase-1-data-ingestion" / "data" / "raw_reviews"
ERROR_RATE_HALT_THRESHOLD = 0.05


class PreprocessingPipeline:
    def __init__(
        self,
        phase1_dir: str = str(DEFAULT_PHASE1_DIR),
        data_dir: str = "data",
        emoji_mode: str = "remove",
        dry_run: bool = False,
    ):
        self._phase1_dir = Path(phase1_dir)
        self._store = NormalizedStore(Path(data_dir) / "normalized_reviews")
        self._reports_dir = Path(data_dir) / "quality_reports"
        self._index_dir = Path(data_dir) / "dedup_index"
        self._dry_run = dry_run
        self._batch_id = str(uuid.uuid4())

        self._html_cleaner = HTMLCleaner()
        self._emoji_handler = EmojiHandler(mode=emoji_mode)
        self._ws_cleaner = WhitespaceCleaner()
        self._char_filter = SpecialCharFilter()
        self._lang_detector = LanguageDetector()
        self._quality_scorer = QualityScorer()
        self._exact_dedup = ExactDeduplicator(self._index_dir / "exact_hashes.json")
        self._near_dedup = NearDupDetector()
        self._rating_norm = RatingNormalizer()
        self._date_norm = DateNormalizer()
        self._platform_mapper = PlatformMapper()

    @property
    def batch_id(self) -> str:
        return self._batch_id

    def run(self, date_str: Optional[str] = None) -> dict:
        """Load Phase 1 JSONL files, process all reviews, and emit a quality report."""
        target_date = date_str or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        run_start = datetime.now(timezone.utc)

        logger.info(
            "phase=2 event=pipeline_start batch=%s date=%s dry_run=%s",
            self._batch_id, target_date, self._dry_run,
        )

        raw_records = self._load_raw_reviews(target_date)
        logger.info("phase=2 event=loaded_raw total=%d", len(raw_records))

        if not raw_records:
            logger.warning("phase=2 event=no_input date=%s", target_date)
            return self._empty_report(target_date, run_start)

        source_batch_ids = list({r.get("ingestion_batch_id", "") for r in raw_records})
        batch = PreprocessingBatch(
            batch_id=self._batch_id,
            source_batch_ids=source_batch_ids,
            started_at=run_start.isoformat(),
            total_input=len(raw_records),
        )

        normalized: list[NormalizedReview] = []
        excluded: list[dict] = []
        stage_stats: dict[str, dict] = {
            "html_cleaning": {"modified": 0},
            "language_filter": {"excluded": 0, "language_breakdown": {}},
            "exact_dedup": {"removed": 0},
            "near_dup": {"removed": 0},
            "quality_filter": {"excluded": 0, "scores": []},
        }

        for raw in raw_records:
            result = self._process_one(raw, stage_stats)
            if result is None:
                continue
            review, excl = result
            if excl:
                excluded.append(excl)
                continue
            normalized.append(review)

        batch.total_output = len(normalized)
        batch.filtered_non_english = stage_stats["language_filter"]["excluded"]
        batch.filtered_duplicates = (
            stage_stats["exact_dedup"]["removed"] + stage_stats["near_dup"]["removed"]
        )
        batch.filtered_low_quality = stage_stats["quality_filter"]["excluded"]
        batch.status = "completed"
        batch.completed_at = datetime.now(timezone.utc).isoformat()

        if not self._dry_run:
            if normalized:
                self._store.write(normalized, self._batch_id)
            if excluded:
                self._store.write_excluded(excluded, self._batch_id)
            self._store.write_batch_manifest(batch.model_dump(), self._batch_id)
            self._exact_dedup.save_index()

        run_end = datetime.now(timezone.utc)
        report = self._build_report(batch, stage_stats, normalized, run_start, run_end)

        if not self._dry_run:
            self._write_report(report)

        error_rate = 1 - (len(normalized) / len(raw_records)) if raw_records else 0.0
        if error_rate > ERROR_RATE_HALT_THRESHOLD:
            logger.warning(
                "phase=2 event=high_exclusion_rate rate=%.1f%% — check quality report",
                error_rate * 100,
            )

        logger.info(
            "phase=2 event=pipeline_complete batch=%s input=%d output=%d excluded=%d duration_s=%.1f",
            self._batch_id,
            len(raw_records),
            len(normalized),
            len(excluded),
            (run_end - run_start).total_seconds(),
        )
        return report

    # ── Per-review processing ────────────────────────────────────────────────

    def _process_one(
        self, raw: dict, stage_stats: dict
    ) -> Optional[tuple[Optional[NormalizedReview], Optional[dict]]]:
        """Process a single raw review through all stages.

        Returns (NormalizedReview, None) on success, or (None, exclusion_dict) if excluded.
        Returns None on unrecoverable parse error.
        """
        review_id = raw.get("id", "")
        raw_text = raw.get("raw_text", "")
        platform_raw = raw.get("source_platform", "")
        rating_raw = raw.get("rating")
        published_at_raw = raw.get("published_at", "")

        if not raw_text or not raw_text.strip():
            return None

        filters_applied: list[str] = []

        # Stage 1-4: Cleaning
        text, html_modified = self._html_cleaner.clean(raw_text)
        if html_modified:
            stage_stats["html_cleaning"]["modified"] += 1
            filters_applied.append("html_strip")

        text, emoji_modified = self._emoji_handler.handle(text)
        if emoji_modified:
            filters_applied.append("emoji_remove")

        text = self._ws_cleaner.clean(text)
        text = self._char_filter.clean(text)

        if not text.strip():
            return None, {
                "source_review_id": review_id,
                "exclusion_reason": "empty_after_cleaning",
                "platform": platform_raw,
            }

        # Stage 5: Language detection
        lang, lang_conf = self._lang_detector.detect(text)
        if lang != "en":
            stage_stats["language_filter"]["excluded"] += 1
            breakdown = stage_stats["language_filter"]["language_breakdown"]
            breakdown[lang] = breakdown.get(lang, 0) + 1
            filters_applied.append("language_filter")
            return None, {
                "source_review_id": review_id,
                "exclusion_reason": "non_english",
                "detected_language": lang,
                "language_confidence": lang_conf,
                "platform": platform_raw,
            }

        # Stage 6: Exact deduplication
        is_exact_dup, canonical_id = self._exact_dedup.is_duplicate(text)
        if is_exact_dup:
            stage_stats["exact_dedup"]["removed"] += 1
            normalized_id = str(uuid.uuid4())
            review = self._build_normalized(
                normalized_id, review_id, text, rating_raw, lang,
                platform_raw, published_at_raw, filters_applied,
                is_duplicate=True, duplicate_of_id=canonical_id,
            )
            return review, None

        self._exact_dedup.register(text, review_id)

        # Stage 7: Near-duplicate detection
        is_near_dup, near_canonical = self._near_dedup.is_near_duplicate(text)
        if is_near_dup:
            stage_stats["near_dup"]["removed"] += 1
            normalized_id = str(uuid.uuid4())
            review = self._build_normalized(
                normalized_id, review_id, text, rating_raw, lang,
                platform_raw, published_at_raw, filters_applied,
                is_duplicate=True, duplicate_of_id=near_canonical,
            )
            return review, None

        self._near_dedup.register(text, review_id)

        # Stages 8-10: Normalization and quality scoring
        normalized_id = str(uuid.uuid4())
        review = self._build_normalized(
            normalized_id, review_id, text, rating_raw, lang,
            platform_raw, published_at_raw, filters_applied,
            is_duplicate=False,
        )

        stage_stats["quality_filter"]["scores"].append(review.quality_score)
        if not review.passes_quality_threshold:
            stage_stats["quality_filter"]["excluded"] += 1
            filters_applied.append("quality_filter")

        return review, None

    def _build_normalized(
        self,
        normalized_id: str,
        source_review_id: str,
        clean_text: str,
        rating_raw: Optional[int],
        language: str,
        platform_raw: str,
        published_at_raw: str,
        filters_applied: list[str],
        is_duplicate: bool,
        duplicate_of_id: Optional[str] = None,
    ) -> NormalizedReview:
        platform = self._platform_mapper.map(platform_raw)
        normalized_rating = self._rating_norm.normalize(rating_raw, platform)
        published_at = self._date_norm.normalize(published_at_raw)
        quality_score = self._quality_scorer.score(clean_text)
        word_count = self._quality_scorer.word_count(clean_text)
        sentence_count = self._quality_scorer.sentence_count(clean_text)

        return NormalizedReview(
            id=normalized_id,
            source_review_id=source_review_id,
            clean_text=clean_text,
            normalized_rating=normalized_rating,
            language=language,
            word_count=word_count,
            sentence_count=sentence_count,
            quality_score=quality_score,
            is_duplicate=is_duplicate,
            duplicate_of_id=duplicate_of_id,
            platform=platform,
            published_at=published_at,
            normalized_at=datetime.now(timezone.utc).isoformat(),
            filters_applied=list(filters_applied),
        )

    # ── Phase 1 data loading ─────────────────────────────────────────────────

    def _load_raw_reviews(self, date_str: str) -> list[dict]:
        """Scan Phase 1 JSONL files for the given date and return raw dicts."""
        records: list[dict] = []
        if not self._phase1_dir.exists():
            logger.error("phase=2 event=phase1_dir_missing path=%s", self._phase1_dir)
            return records

        for platform_dir in sorted(self._phase1_dir.iterdir()):
            if not platform_dir.is_dir():
                continue
            date_dir = platform_dir / date_str
            if not date_dir.exists():
                continue
            for jsonl_path in sorted(date_dir.glob("*.jsonl")):
                if jsonl_path.name.endswith(".errors.jsonl"):
                    continue
                records.extend(self._read_raw_jsonl(jsonl_path))

        return records

    def _read_raw_jsonl(self, path: Path) -> list[dict]:
        records: list[dict] = []
        with path.open("r", encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    logger.warning("Skipping malformed JSONL at %s:%d — %s", path, lineno, exc)
        logger.debug("phase=2 action=load_raw path=%s records=%d", path, len(records))
        return records

    # ── Report ───────────────────────────────────────────────────────────────

    def _build_report(
        self,
        batch: PreprocessingBatch,
        stage_stats: dict,
        normalized: list[NormalizedReview],
        run_start: datetime,
        run_end: datetime,
    ) -> dict:
        quality_scores = stage_stats["quality_filter"]["scores"]
        passing = [r for r in normalized if r.passes_quality_threshold]
        rated = [r for r in normalized if r.normalized_rating is not None]

        return {
            "phase": 2,
            "batch_id": self._batch_id,
            "run_date": run_start.isoformat(),
            "duration_seconds": round((run_end - run_start).total_seconds(), 2),
            "dry_run": self._dry_run,
            "total_input": batch.total_input,
            "total_output": batch.total_output,
            "stages": {
                "html_cleaning": {
                    "modified": stage_stats["html_cleaning"]["modified"],
                },
                "language_filter": {
                    "excluded": stage_stats["language_filter"]["excluded"],
                    "language_breakdown": stage_stats["language_filter"]["language_breakdown"],
                },
                "exact_dedup": {
                    "removed": stage_stats["exact_dedup"]["removed"],
                },
                "near_dup": {
                    "removed": stage_stats["near_dup"]["removed"],
                },
                "quality_filter": {
                    "excluded": stage_stats["quality_filter"]["excluded"],
                    "avg_quality_score": round(
                        sum(quality_scores) / len(quality_scores), 4
                    ) if quality_scores else 0.0,
                },
            },
            "output_quality": {
                "avg_word_count": round(
                    sum(r.word_count for r in normalized) / len(normalized), 1
                ) if normalized else 0,
                "avg_quality_score": round(
                    sum(r.quality_score for r in normalized) / len(normalized), 4
                ) if normalized else 0.0,
                "rating_coverage": round(
                    len(rated) / len(normalized), 4
                ) if normalized else 0.0,
                "passing_quality_threshold": len(passing),
                "quality_threshold": QUALITY_THRESHOLD,
            },
        }

    def _empty_report(self, date_str: str, run_start: datetime) -> dict:
        return {
            "phase": 2,
            "batch_id": self._batch_id,
            "run_date": run_start.isoformat(),
            "duration_seconds": 0.0,
            "dry_run": self._dry_run,
            "total_input": 0,
            "total_output": 0,
            "stages": {},
            "output_quality": {},
            "note": f"No Phase 1 reviews found for date {date_str}",
        }

    def _write_report(self, report: dict) -> None:
        self._reports_dir.mkdir(parents=True, exist_ok=True)
        out = self._reports_dir / f"phase2_{self._batch_id}.json"
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("phase=2 event=report_written path=%s", out)


# ── CLI entry point ──────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 2 — Preprocessing Pipeline")
    parser.add_argument(
        "--phase1-dir",
        default=str(DEFAULT_PHASE1_DIR),
        help="Path to Phase 1 raw_reviews directory",
    )
    parser.add_argument("--data-dir", default="data", help="Root data directory for output")
    parser.add_argument("--date", default=None, help="Process reviews from this date (YYYY-MM-DD)")
    parser.add_argument("--emoji-mode", default="remove", choices=["remove", "replace"])
    parser.add_argument("--dry-run", action="store_true", help="Process but skip writing to disk")
    args = parser.parse_args()

    pipeline = PreprocessingPipeline(
        phase1_dir=args.phase1_dir,
        data_dir=args.data_dir,
        emoji_mode=args.emoji_mode,
        dry_run=args.dry_run,
    )
    report = pipeline.run(date_str=args.date)

    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
