"""Phase 1 — Ingestion Pipeline Orchestrator.

Runs all configured source collectors, validates each record against the
RawReview schema, writes valid records to immutable JSONL storage, logs
rejected records to error files, and emits a quality report.

Usage:
    python ingestion_pipeline.py                     # uses config.json in CWD
    python ingestion_pipeline.py --config my.json    # custom config path
    python ingestion_pipeline.py --since 2024-01-01  # only fetch after date
    python ingestion_pipeline.py --dry-run           # fetch but skip writing
"""

import argparse
import json
import logging
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from collectors.app_store import AppStoreCollector
from collectors.community import CommunityCollector
from collectors.google_play import GooglePlayCollector
from collectors.reddit import RedditCollector
from collectors.social import SocialCollector
from collectors.base import CollectorInterface
from models.raw_review import RawReview
from models.ingestion_batch import IngestionBatch, PlatformStats
from storage.raw_store import RawStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("phase1.pipeline")

ERROR_RATE_HALT_THRESHOLD = 0.05  # halt if > 5% of fetched records are rejected


class IngestionPipeline:
    def __init__(
        self,
        config: dict,
        data_dir: str = "data",
        dry_run: bool = False,
    ):
        self._config = config
        self._store = RawStore(Path(data_dir) / "raw_reviews")
        self._reports_dir = Path(data_dir) / "quality_reports"
        self._dry_run = dry_run
        self._batch_id = str(uuid.uuid4())

    @property
    def batch_id(self) -> str:
        return self._batch_id

    def run(self, since_date: Optional[datetime] = None) -> dict:
        """Execute all enabled collectors and return the quality report."""
        run_start = datetime.now(timezone.utc)
        logger.info(
            "phase=1 event=pipeline_start batch=%s dry_run=%s",
            self._batch_id, self._dry_run,
        )

        collectors = self._build_collectors()
        platform_stats: dict[str, PlatformStats] = {}
        batches: list[IngestionBatch] = []

        for platform, collector in collectors.items():
            stats, batch = self._run_collector(collector, platform, since_date)
            platform_stats[platform] = stats
            batches.append(batch)

        run_end = datetime.now(timezone.utc)
        report = self._build_report(platform_stats, run_start, run_end)

        if not self._dry_run:
            self._write_report(report)

        # Halt signal: upstream phases should check error_rate before proceeding
        if report["error_rate"] > ERROR_RATE_HALT_THRESHOLD:
            logger.error(
                "phase=1 event=halt_threshold_exceeded error_rate=%.2f%%",
                report["error_rate"] * 100,
            )

        logger.info(
            "phase=1 event=pipeline_complete batch=%s fetched=%d valid=%d rejected=%d duration_s=%.1f",
            self._batch_id,
            report["total_fetched"],
            report["total_valid"],
            report["total_rejected"],
            report["duration_seconds"],
        )
        return report

    # ── Collector execution ──────────────────────────────────────────────────

    def _run_collector(
        self,
        collector: CollectorInterface,
        platform: str,
        since_date: Optional[datetime],
    ) -> tuple[PlatformStats, IngestionBatch]:
        stats = PlatformStats()
        started_at = datetime.now(timezone.utc).isoformat()
        platform_cfg = self._config.get(platform, {})
        batch = IngestionBatch(
            batch_id=self._batch_id,
            platform=platform,
            started_at=started_at,
            query_params=platform_cfg,
        )

        logger.info("phase=1 event=collector_start platform=%s batch=%s", platform, self._batch_id)

        try:
            if not collector.validate_credentials():
                logger.error("phase=1 event=credential_failure platform=%s", platform)
                batch.status = "failed"
                batch.failure_reason = "credential_validation_failed"
                return stats, batch

            limit = platform_cfg.get("limit", 500)
            query = platform_cfg.get("query", "")
            raw_reviews = collector.fetch(query=query, limit=limit, since_date=since_date)
            stats.fetched = len(raw_reviews)

            valid_reviews: list[RawReview] = []
            rejected_records: list[dict] = []

            for review in raw_reviews:
                errors = review.validation_errors()
                if errors:
                    stats.record_rejection(errors[0])
                    rejected_records.append({
                        "review_id": review.id,
                        "platform": review.source_platform,
                        "rejection_reasons": errors,
                        "raw_text_preview": (review.raw_text or "")[:120],
                        "published_at": review.published_at,
                    })
                else:
                    valid_reviews.append(review)
                    stats.valid += 1

            if not self._dry_run:
                if valid_reviews:
                    self._store.write(valid_reviews, self._batch_id)
                if rejected_records:
                    self._store.write_error_log(rejected_records, self._batch_id, platform)
                self._store.write_batch_manifest(
                    batch.model_dump(), self._batch_id, platform
                )

            batch.total_fetched = stats.fetched
            batch.total_valid = stats.valid
            batch.total_rejected = stats.rejected
            batch.status = "completed"
            batch.completed_at = datetime.now(timezone.utc).isoformat()

            logger.info(
                "phase=1 event=collector_complete platform=%s fetched=%d valid=%d rejected=%d",
                platform, stats.fetched, stats.valid, stats.rejected,
            )

        except Exception as exc:
            logger.exception("phase=1 event=collector_error platform=%s error=%s", platform, exc)
            batch.status = "partial"
            batch.failure_reason = str(exc)

        return stats, batch

    # ── Collector factory ────────────────────────────────────────────────────

    def _build_collectors(self) -> dict[str, CollectorInterface]:
        cfg = self._config
        collectors: dict[str, CollectorInterface] = {}

        if cfg.get("app_store", {}).get("enabled", True):
            collectors["app_store"] = AppStoreCollector(
                app_id=cfg.get("app_store", {}).get("app_id", "324684580"),
                batch_id=self._batch_id,
            )

        if cfg.get("google_play", {}).get("enabled", True):
            collectors["google_play"] = GooglePlayCollector(
                package=cfg.get("google_play", {}).get("package", "com.spotify.music"),
                batch_id=self._batch_id,
                country=cfg.get("google_play", {}).get("country", "us"),
                lang=cfg.get("google_play", {}).get("lang", "en"),
            )

        if cfg.get("reddit", {}).get("enabled", False):
            reddit_cfg = cfg["reddit"]
            collectors["reddit"] = RedditCollector(
                client_id=reddit_cfg["client_id"],
                client_secret=reddit_cfg["client_secret"],
                batch_id=self._batch_id,
            )

        if cfg.get("community", {}).get("enabled", True):
            collectors["community"] = CommunityCollector(batch_id=self._batch_id)

        if cfg.get("social", {}).get("enabled", False):
            social_cfg = cfg["social"]
            collectors["social"] = SocialCollector(
                bearer_token=social_cfg["bearer_token"],
                batch_id=self._batch_id,
            )

        return collectors

    # ── Report ───────────────────────────────────────────────────────────────

    def _build_report(
        self,
        platform_stats: dict[str, PlatformStats],
        run_start: datetime,
        run_end: datetime,
    ) -> dict:
        total_fetched = sum(s.fetched for s in platform_stats.values())
        total_valid = sum(s.valid for s in platform_stats.values())
        total_rejected = sum(s.rejected for s in platform_stats.values())

        return {
            "phase": 1,
            "batch_id": self._batch_id,
            "run_date": run_start.isoformat(),
            "duration_seconds": (run_end - run_start).total_seconds(),
            "dry_run": self._dry_run,
            "platforms": {
                platform: {
                    "fetched": stats.fetched,
                    "valid": stats.valid,
                    "rejected": stats.rejected,
                    "rejection_reasons": stats.rejection_reasons,
                }
                for platform, stats in platform_stats.items()
            },
            "total_fetched": total_fetched,
            "total_valid": total_valid,
            "total_rejected": total_rejected,
            "error_rate": round(total_rejected / total_fetched, 4) if total_fetched else 0.0,
        }

    def _write_report(self, report: dict) -> None:
        self._reports_dir.mkdir(parents=True, exist_ok=True)
        out = self._reports_dir / f"phase1_{self._batch_id}.json"
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("phase=1 event=report_written path=%s", out)


# ── CLI entry point ──────────────────────────────────────────────────────────

def _load_config(path: str) -> dict:
    config_path = Path(path)
    if not config_path.exists():
        logger.warning("Config file not found at %s — using defaults", path)
        return {}
    return json.loads(config_path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 1 — Data Ingestion Pipeline")
    parser.add_argument("--config", default="config.json", help="Path to config JSON file")
    parser.add_argument("--since", default=None, help="Only fetch reviews after this date (YYYY-MM-DD)")
    parser.add_argument("--data-dir", default="data", help="Root data directory")
    parser.add_argument("--dry-run", action="store_true", help="Fetch but skip writing to disk")
    args = parser.parse_args()

    config = _load_config(args.config)
    since_date: Optional[datetime] = None
    if args.since:
        try:
            since_date = datetime.strptime(args.since, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            logger.error("Invalid --since date format. Expected YYYY-MM-DD, got: %s", args.since)
            return 1

    pipeline = IngestionPipeline(config=config, data_dir=args.data_dir, dry_run=args.dry_run)
    report = pipeline.run(since_date=since_date)

    print(json.dumps(report, indent=2))
    return 0 if report["error_rate"] <= ERROR_RATE_HALT_THRESHOLD else 1


if __name__ == "__main__":
    sys.exit(main())
