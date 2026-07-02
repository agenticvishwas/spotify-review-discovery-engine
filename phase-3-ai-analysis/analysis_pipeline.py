"""Phase 3 — AI Analysis Pipeline Orchestrator.

Reads NormalizedReview JSONL files from Phase 2 output, runs LLM extraction
on each eligible review, writes AnalyzedReview records to JSONL, and emits
an analysis quality report.

Usage:
    python analysis_pipeline.py
    python analysis_pipeline.py --phase2-dir ../phase-2-preprocessing/data/normalized_reviews
    python analysis_pipeline.py --date 2026-06-29
    python analysis_pipeline.py --dry-run
    python analysis_pipeline.py --concurrency 5

    # Provider selection (default: anthropic)
    python analysis_pipeline.py --provider anthropic --api-key sk-ant-...
    python analysis_pipeline.py --provider groq     --api-key gsk_...
    python analysis_pipeline.py --provider ollama   --model mistral
"""

import argparse
import asyncio
import json
import logging
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent / "phase-2-preprocessing"))
sys.path.insert(0, str(Path(__file__).parent))  # phase-3 at index 0 so its storage/ wins over phase-2's

from models.normalized_review import NormalizedReview  # noqa: E402

from analyzers.llm_client import LLMClient, CURRENT_PROMPT_VERSION
from analyzers.batch_processor import BatchProcessor, BatchStats
from storage.analyzed_store import AnalyzedStore
from schemas.analyzed_review import AnalyzedReview

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("phase3.pipeline")

DEFAULT_PHASE2_DIR = Path("..") / "phase-2-preprocessing" / "data" / "normalized_reviews"
ERROR_RATE_HALT_THRESHOLD = 0.05


class AnalysisPipeline:
    def __init__(
        self,
        phase2_dir: str = str(DEFAULT_PHASE2_DIR),
        data_dir: str = "data",
        concurrency: int = 5,
        provider: str = "anthropic",
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        prompt_version: str = CURRENT_PROMPT_VERSION,
        dry_run: bool = False,
    ):
        self._phase2_dir = Path(phase2_dir)
        self._store = AnalyzedStore(Path(data_dir) / "analyzed_reviews")
        self._reports_dir = Path(data_dir) / "quality_reports"
        self._dry_run = dry_run
        self._batch_id = str(uuid.uuid4())
        self._concurrency = concurrency
        self._provider = provider
        self._api_key = api_key
        self._model = model
        self._prompt_version = prompt_version

    @property
    def batch_id(self) -> str:
        return self._batch_id

    def run(self, date_str: Optional[str] = None) -> dict:
        """Synchronous entry point — runs the async pipeline."""
        return asyncio.run(self._run_async(date_str))

    async def _run_async(self, date_str: Optional[str] = None) -> dict:
        explicit_date = date_str is not None
        target_date = date_str or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        run_start = datetime.now(timezone.utc)

        logger.info(
            "phase=3 event=pipeline_start batch=%s date=%s dry_run=%s concurrency=%d provider=%s model=%s",
            self._batch_id, target_date, self._dry_run, self._concurrency,
            self._provider, self._model or "default",
        )

        normalized = self._load_normalized_reviews(target_date)

        if not normalized and not explicit_date:
            fallback = self._find_most_recent_date(exclude=target_date)
            if fallback:
                logger.warning(
                    "phase=3 event=date_fallback no_data_for=%s falling_back_to=%s",
                    target_date, fallback,
                )
                target_date = fallback
                normalized = self._load_normalized_reviews(target_date)

        logger.info("phase=3 event=loaded_normalized total=%d date=%s", len(normalized), target_date)

        if not normalized:
            logger.warning("phase=3 event=no_input date=%s", target_date)
            return self._empty_report(target_date, run_start)

        already_analyzed_ids: set[str] = set()
        if not self._dry_run:
            already_analyzed_ids = self._store.load_analyzed_ids(target_date)
            if already_analyzed_ids:
                logger.info(
                    "phase=3 event=resume already_analyzed=%d", len(already_analyzed_ids)
                )

        llm_client = LLMClient(
            provider=self._provider,
            api_key=self._api_key,
            model=self._model,
            prompt_version=self._prompt_version,
        )
        processor = BatchProcessor(llm_client=llm_client, concurrency=self._concurrency)

        results: list[AnalyzedReview] = []

        def on_result(review: AnalyzedReview) -> None:
            results.append(review)
            if not self._dry_run:
                self._store.append(review, self._batch_id, target_date)

        stats = await processor.process(
            reviews=normalized,
            on_result=on_result,
            already_analyzed_ids=already_analyzed_ids,
        )

        run_end = datetime.now(timezone.utc)
        report = self._build_report(stats, results, target_date, run_start, run_end)

        if not self._dry_run:
            self._write_report(report)

        if stats.total > 0 and stats.as_dict()["failure_rate"] > ERROR_RATE_HALT_THRESHOLD:
            logger.error(
                "phase=3 event=high_failure_rate rate=%.1f%% — investigate before Phase 4",
                stats.as_dict()["failure_rate"] * 100,
            )

        logger.info(
            "phase=3 event=pipeline_complete batch=%s analyzed=%d failed=%d duration_s=%.1f",
            self._batch_id,
            stats.success,
            stats.failed,
            (run_end - run_start).total_seconds(),
        )
        return report

    # ── Phase 2 data loading ─────────────────────────────────────────────────

    def _find_most_recent_date(self, exclude: Optional[str] = None) -> Optional[str]:
        """Return the most recent YYYY-MM-DD folder that contains at least one JSONL file."""
        if not self._phase2_dir.exists():
            return None
        candidates: set[str] = set()
        for platform_dir in self._phase2_dir.iterdir():
            if not platform_dir.is_dir() or platform_dir.name in ("excluded", "manifests"):
                continue
            for date_dir in platform_dir.iterdir():
                if not date_dir.is_dir():
                    continue
                if date_dir.name == exclude:
                    continue
                if any(date_dir.glob("*.jsonl")):
                    candidates.add(date_dir.name)
        return max(candidates) if candidates else None

    def _load_normalized_reviews(self, date_str: str) -> list[NormalizedReview]:
        reviews: list[NormalizedReview] = []
        if not self._phase2_dir.exists():
            logger.error("phase=3 event=phase2_dir_missing path=%s", self._phase2_dir)
            return reviews

        for platform_dir in sorted(self._phase2_dir.iterdir()):
            if not platform_dir.is_dir() or platform_dir.name in ("excluded", "manifests"):
                continue
            date_dir = platform_dir / date_str
            if not date_dir.exists():
                continue
            for jsonl_path in sorted(date_dir.glob("*.jsonl")):
                reviews.extend(self._read_normalized_jsonl(jsonl_path))

        return reviews

    def _read_normalized_jsonl(self, path: Path) -> list[NormalizedReview]:
        records: list[NormalizedReview] = []
        with path.open("r", encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(NormalizedReview.model_validate_json(line))
                except Exception as exc:
                    logger.warning(
                        "Skipping malformed JSONL at %s:%d — %s", path, lineno, exc
                    )
        logger.debug("phase=3 action=load_normalized path=%s records=%d", path, len(records))
        return records

    # ── Report ───────────────────────────────────────────────────────────────

    def _build_report(
        self,
        stats: BatchStats,
        results: list[AnalyzedReview],
        date_str: str,
        run_start: datetime,
        run_end: datetime,
    ) -> dict:
        successes = [r for r in results if r.analysis_status == "success"]
        low_conf = [r for r in results if r.analysis_status == "low_confidence"]
        failed = [r for r in results if r.analysis_status == "failed"]

        avg_conf = (
            round(sum(r.confidence_score for r in successes) / len(successes), 4)
            if successes else 0.0
        )
        friction_rate = (
            round(sum(1 for r in successes if r.discovery_friction_detected) / len(successes), 4)
            if successes else 0.0
        )
        sentiment_dist: dict[str, int] = {}
        for r in successes:
            sentiment_dist[r.sentiment] = sentiment_dist.get(r.sentiment, 0) + 1

        return {
            "phase": 3,
            "batch_id": self._batch_id,
            "run_date": run_start.isoformat(),
            "target_date": date_str,
            "duration_seconds": round((run_end - run_start).total_seconds(), 2),
            "dry_run": self._dry_run,
            "provider": self._provider,
            "model": self._model or "default",
            "prompt_version": self._prompt_version,
            "totals": stats.as_dict(),
            "output_quality": {
                "avg_confidence_score": avg_conf,
                "low_confidence_count": len(low_conf),
                "low_confidence_threshold": 0.5,
                "discovery_friction_rate": friction_rate,
                "sentiment_distribution": sentiment_dist,
                "total_tokens_used": stats.total_tokens,
            },
        }

    def _empty_report(self, date_str: str, run_start: datetime) -> dict:
        return {
            "phase": 3,
            "batch_id": self._batch_id,
            "run_date": run_start.isoformat(),
            "target_date": date_str,
            "duration_seconds": 0.0,
            "dry_run": self._dry_run,
            "prompt_version": self._prompt_version,
            "totals": {},
            "output_quality": {},
            "note": f"No Phase 2 normalized reviews found for date {date_str}",
        }

    def _write_report(self, report: dict) -> None:
        self._reports_dir.mkdir(parents=True, exist_ok=True)
        out = self._reports_dir / f"phase3_{self._batch_id}.json"
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("phase=3 event=report_written path=%s", out)


# ── CLI entry point ──────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 3 — AI Analysis Pipeline")
    parser.add_argument(
        "--phase2-dir",
        default=str(DEFAULT_PHASE2_DIR),
        help="Path to Phase 2 normalized_reviews directory",
    )
    parser.add_argument("--data-dir", default="data", help="Root data directory for output")
    parser.add_argument("--date", default=None, help="Process reviews from this date (YYYY-MM-DD)")
    parser.add_argument("--concurrency", type=int, default=5, help="Max concurrent LLM calls")
    parser.add_argument("--prompt-version", default=CURRENT_PROMPT_VERSION, help="Prompt version to use")
    parser.add_argument(
        "--provider",
        default="anthropic",
        choices=["anthropic", "groq", "ollama"],
        help="LLM provider (default: anthropic)",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="API key for the selected provider (or set ANTHROPIC_API_KEY / GROQ_API_KEY)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override default model for the selected provider",
    )
    parser.add_argument("--dry-run", action="store_true", help="Process but skip writing to disk")
    args = parser.parse_args()

    pipeline = AnalysisPipeline(
        phase2_dir=args.phase2_dir,
        data_dir=args.data_dir,
        concurrency=args.concurrency,
        provider=args.provider,
        api_key=args.api_key,
        model=args.model,
        prompt_version=args.prompt_version,
        dry_run=args.dry_run,
    )
    report = pipeline.run(date_str=args.date)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
