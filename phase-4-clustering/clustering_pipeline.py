"""Phase 4 — Clustering & Pattern Recognition Pipeline.

Reads AnalyzedReview JSONL from Phase 3, optionally enriches with NormalizedReview
data from Phase 2, generates embeddings, clusters semantically, labels themes via
LLM, computes trends, and writes ReviewCluster JSONL.

Usage:
    python clustering_pipeline.py
    python clustering_pipeline.py --phase3-dir ../phase-3-ai-analysis/data/analyzed_reviews
    python clustering_pipeline.py --phase2-dir ../phase-2-preprocessing/data/normalized_reviews
    python clustering_pipeline.py --date 2026-06-29
    python clustering_pipeline.py --dry-run
    python clustering_pipeline.py --skip-labeling   # skip LLM calls for theme labeling

    # Provider selection (default: anthropic)
    python clustering_pipeline.py --provider anthropic --api-key sk-ant-...
    python clustering_pipeline.py --provider groq     --api-key gsk_...
    python clustering_pipeline.py --provider ollama   --model llama3.1
    python clustering_pipeline.py --provider ollama   --model mistral

    # Throughput tuning (reduce TPM pressure)
    python clustering_pipeline.py --provider groq --label-batch-size 15 --label-concurrency 5
    python clustering_pipeline.py --provider ollama --label-batch-size 5 --label-concurrency 1
"""

import argparse
import json
import logging
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Insert sibling phases first, then phase-4 last so phase-4's packages win
sys.path.insert(0, str(Path(__file__).parent.parent / "phase-2-preprocessing"))
sys.path.insert(0, str(Path(__file__).parent.parent / "phase-3-ai-analysis"))
sys.path.insert(0, str(Path(__file__).parent))

from schemas.analyzed_review import AnalyzedReview  # noqa: E402
from models.normalized_review import NormalizedReview  # noqa: E402

from embeddings.embedding_engine import EmbeddingEngine, ReviewEmbeddingInput
from embeddings.embedding_cache import EmbeddingCache
from embeddings.umap_reducer import UMAPReducer
from clustering.hdbscan_clusterer import HDBSCANClusterer
from clustering.fallback_clusterer import FallbackClusterer
from clustering.cluster_assembler import ClusterAssembler, ReviewRecord
from themes.theme_labeler import ThemeLabeler
from themes.trend_analyzer import TrendAnalyzer
from cluster_models.review_cluster import ReviewCluster
from storage.cluster_store import ClusterStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("phase4.pipeline")

DEFAULT_PHASE3_DIR = Path("..") / "phase-3-ai-analysis" / "data" / "analyzed_reviews"
DEFAULT_PHASE2_DIR = Path("..") / "phase-2-preprocessing" / "data" / "normalized_reviews"
NOISE_RATE_WARN_THRESHOLD = 0.10


class ClusteringPipeline:
    def __init__(
        self,
        phase3_dir: str = str(DEFAULT_PHASE3_DIR),
        phase2_dir: Optional[str] = str(DEFAULT_PHASE2_DIR),
        data_dir: str = "data",
        provider: str = "anthropic",
        api_key: Optional[str] = None,
        labeling_model: Optional[str] = None,
        label_batch_size: int = 10,
        label_concurrency: int = 3,
        dry_run: bool = False,
        skip_labeling: bool = False,
    ):
        from themes.theme_labeler import PROVIDER_DEFAULTS
        if provider not in PROVIDER_DEFAULTS:
            raise ValueError(f"Unknown provider '{provider}'. Choose from: {list(PROVIDER_DEFAULTS)}")

        self._phase3_dir = Path(phase3_dir)
        self._phase2_dir = Path(phase2_dir) if phase2_dir else None
        self._store = ClusterStore(Path(data_dir) / "clusters")
        self._cache = EmbeddingCache(Path(data_dir) / "embeddings_cache")
        self._reports_dir = Path(data_dir) / "quality_reports"
        self._provider = provider
        self._api_key = api_key
        self._labeling_model = labeling_model or PROVIDER_DEFAULTS[provider]["model"]
        self._label_batch_size = label_batch_size
        self._label_concurrency = label_concurrency
        self._dry_run = dry_run
        self._skip_labeling = skip_labeling
        self._batch_id = str(uuid.uuid4())

    @property
    def batch_id(self) -> str:
        return self._batch_id

    def run(self, date_str: Optional[str] = None) -> dict:
        run_start = datetime.now(timezone.utc)
        explicit_date = date_str is not None
        target_date = date_str or run_start.strftime("%Y-%m-%d")

        logger.info(
            "phase=4 event=pipeline_start batch=%s date=%s dry_run=%s "
            "skip_labeling=%s provider=%s model=%s",
            self._batch_id, target_date, self._dry_run,
            self._skip_labeling, self._provider, self._labeling_model,
        )

        # ── Step 1: Load Phase 3 data ─────────────────────────────────────────
        analyzed = self._load_analyzed(target_date)
        if not analyzed and not explicit_date:
            fallback = self._find_most_recent_date()
            if fallback:
                logger.warning("phase=4 event=date_fallback using=%s", fallback)
                target_date = fallback
                analyzed = self._load_analyzed(target_date)

        if not analyzed:
            logger.warning("phase=4 event=no_input date=%s", target_date)
            return self._empty_report(target_date, run_start)

        logger.info("phase=4 event=loaded_analyzed total=%d", len(analyzed))

        # ── Step 2: Enrich with Phase 2 data ─────────────────────────────────
        normalized_lookup: dict[str, NormalizedReview] = {}
        if self._phase2_dir and self._phase2_dir.exists():
            normalized_lookup = self._load_normalized(target_date)
            logger.info("phase=4 event=loaded_normalized total=%d", len(normalized_lookup))

        records, text_lookup, date_lookup = self._build_records(analyzed, normalized_lookup)
        logger.info("phase=4 event=built_records total=%d", len(records))

        if not records:
            logger.warning("phase=4 event=no_records_after_build")
            return self._empty_report(target_date, run_start)

        # ── Step 3: Generate embeddings ───────────────────────────────────────
        import numpy as np
        engine = EmbeddingEngine()
        inputs = [ReviewEmbeddingInput(review_id=r.review_id, text=text_lookup[r.review_id]) for r in records]
        # TF-IDF backend must see all texts at once; cache is not passed
        id_to_embedding = engine.embed(inputs)

        embeddings = np.vstack([id_to_embedding[r.review_id] for r in records])

        records_with_emb = []
        for record in records:
            from clustering.cluster_assembler import ReviewRecord as RR
            records_with_emb.append(RR(
                review_id=record.review_id,
                embedding=id_to_embedding[record.review_id],
                platform=record.platform,
                published_at=record.published_at,
                sentiment_score=record.sentiment_score,
                discovery_friction_detected=record.discovery_friction_detected,
                emotion_tags=record.emotion_tags,
                feature_mentions=record.feature_mentions,
            ))

        # ── Step 4: UMAP dimensionality reduction ─────────────────────────────
        reducer = UMAPReducer()
        reduced = reducer.fit_transform(embeddings)

        # ── Step 5: HDBSCAN clustering ────────────────────────────────────────
        clusterer = HDBSCANClusterer()
        labels = clusterer.fit(reduced)

        # ── Step 6: Fallback k-means for noise points ─────────────────────────
        n_noise_before = int((labels == -1).sum())
        fallback = FallbackClusterer()
        labels = fallback.assign(reduced, labels)

        # ── Step 7: Assemble cluster objects ──────────────────────────────────
        assembler = ClusterAssembler()
        cluster_dicts = assembler.build_all(records_with_emb, labels)

        # ── Step 8: LLM theme labeling ────────────────────────────────────────
        if not self._skip_labeling and cluster_dicts:
            labeler = ThemeLabeler(
                provider=self._provider,
                api_key=self._api_key,
                model=self._labeling_model,
            )
            cluster_dicts = labeler.label_all(
                cluster_dicts,
                text_lookup,
                batch_size=self._label_batch_size,
                concurrency=self._label_concurrency,
            )
        else:
            logger.info("phase=4 event=labeling_skipped")
            cluster_dicts = [
                {
                    **c,
                    "label": f"Cluster {i+1}",
                    "theme": "Labeling skipped.",
                    "labeling_confidence": 0.0,
                    "review_required": False,
                    "labeling_model": "none (skipped)",
                    "labeling_prompt_version": "n/a",
                }
                for i, c in enumerate(cluster_dicts)
            ]

        # ── Step 9: Trend analysis ────────────────────────────────────────────
        trend_analyzer = TrendAnalyzer()
        cluster_dicts = trend_analyzer.analyze(cluster_dicts, date_lookup)

        # ── Step 10: Finalize and write ───────────────────────────────────────
        now_iso = datetime.now(timezone.utc).isoformat()
        clusters: list[ReviewCluster] = []
        for cd in cluster_dicts:
            cd = {**cd, "created_at": now_iso}
            clusters.append(ReviewCluster(**cd))

        if not self._dry_run:
            self._store.write_batch(clusters, self._batch_id, target_date)

        run_end = datetime.now(timezone.utc)
        report = self._build_report(
            clusters=clusters,
            n_input=len(analyzed),
            n_noise_before=n_noise_before,
            total_labels=len(labels),
            date_str=target_date,
            run_start=run_start,
            run_end=run_end,
        )

        if not self._dry_run:
            self._write_report(report)

        noise_rate = n_noise_before / max(1, len(labels))
        if noise_rate > NOISE_RATE_WARN_THRESHOLD:
            logger.warning(
                "phase=4 event=high_noise_rate rate=%.1f%% — consider adjusting HDBSCAN params",
                noise_rate * 100,
            )

        logger.info(
            "phase=4 event=pipeline_complete batch=%s clusters=%d duration_s=%.1f",
            self._batch_id, len(clusters), (run_end - run_start).total_seconds(),
        )
        return report

    # ── Data Loading ─────────────────────────────────────────────────────────

    def _load_analyzed(self, date_str: str) -> list[AnalyzedReview]:
        reviews: list[AnalyzedReview] = []
        date_dir = self._phase3_dir / date_str
        if not date_dir.exists():
            return reviews
        for path in sorted(date_dir.glob("*.jsonl")):
            if path.name.endswith(".failed.jsonl"):
                continue
            with path.open("r", encoding="utf-8") as fh:
                for lineno, line in enumerate(fh, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        reviews.append(AnalyzedReview.model_validate_json(line))
                    except Exception as exc:
                        logger.warning("Skipping malformed JSONL at %s:%d — %s", path, lineno, exc)
        return reviews

    def _load_normalized(self, date_str: str) -> dict[str, NormalizedReview]:
        """Return {normalized_review_id: NormalizedReview} for the given date."""
        lookup: dict[str, NormalizedReview] = {}
        if not self._phase2_dir or not self._phase2_dir.exists():
            return lookup
        for platform_dir in sorted(self._phase2_dir.iterdir()):
            if not platform_dir.is_dir() or platform_dir.name in ("excluded", "manifests"):
                continue
            date_dir = platform_dir / date_str
            if not date_dir.exists():
                continue
            for path in sorted(date_dir.glob("*.jsonl")):
                with path.open("r", encoding="utf-8") as fh:
                    for lineno, line in enumerate(fh, 1):
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            nr = NormalizedReview.model_validate_json(line)
                            lookup[nr.id] = nr
                        except Exception as exc:
                            logger.warning("Skipping normalized at %s:%d — %s", path, lineno, exc)
        return lookup

    def _find_most_recent_date(self) -> Optional[str]:
        if not self._phase3_dir.exists():
            return None
        candidates = [
            d.name
            for d in self._phase3_dir.iterdir()
            if d.is_dir() and any(d.glob("*.jsonl"))
        ]
        return max(candidates) if candidates else None

    # ── Record Building ───────────────────────────────────────────────────────

    def _build_records(
        self,
        analyzed: list[AnalyzedReview],
        normalized_lookup: dict[str, NormalizedReview],
    ) -> tuple[list[ReviewRecord], dict[str, str], dict[str, str]]:
        """Build ReviewRecord list, text lookup, and date lookup."""
        records: list[ReviewRecord] = []
        text_lookup: dict[str, str] = {}   # review_id -> embedding/display text
        date_lookup: dict[str, str] = {}   # review_id -> published_at

        import numpy as np

        for ar in analyzed:
            if ar.analysis_status == "failed":
                continue

            nr = normalized_lookup.get(ar.normalized_review_id)

            clean_text = nr.clean_text if nr else None
            platform = nr.platform if nr else "unknown"
            published_at = nr.published_at if nr else ar.analyzed_at

            embedding_text = EmbeddingEngine.build_text(
                clean_text=clean_text,
                jtbd_signal=ar.jtbd_signal,
                primary_complaint=ar.primary_complaint,
                primary_praise=ar.primary_praise,
                user_intent=ar.user_intent,
                feature_mentions=ar.feature_mentions,
            )
            if not embedding_text.strip():
                continue

            records.append(ReviewRecord(
                review_id=ar.id,
                embedding=np.zeros(1),  # placeholder — filled by EmbeddingEngine
                platform=platform,
                published_at=published_at,
                sentiment_score=ar.sentiment_score,
                discovery_friction_detected=ar.discovery_friction_detected,
                emotion_tags=list(ar.emotion_tags),
                feature_mentions=list(ar.feature_mentions),
            ))
            text_lookup[ar.id] = embedding_text
            date_lookup[ar.id] = published_at

        return records, text_lookup, date_lookup

    # ── Reporting ─────────────────────────────────────────────────────────────

    def _build_report(
        self,
        clusters: list[ReviewCluster],
        n_input: int,
        n_noise_before: int,
        total_labels: int,
        date_str: str,
        run_start: datetime,
        run_end: datetime,
    ) -> dict:
        micro = [c for c in clusters if c.is_micro_cluster]
        discovery = [c for c in clusters if c.is_discovery_related]
        needs_review = [c for c in clusters if c.review_required]

        avg_conf = (
            round(sum(c.labeling_confidence for c in clusters) / len(clusters), 4)
            if clusters else 0.0
        )
        trend_dist: dict[str, int] = {}
        for c in clusters:
            trend_dist[c.trend_direction] = trend_dist.get(c.trend_direction, 0) + 1

        return {
            "phase": 4,
            "batch_id": self._batch_id,
            "run_date": run_start.isoformat(),
            "target_date": date_str,
            "duration_seconds": round((run_end - run_start).total_seconds(), 2),
            "dry_run": self._dry_run,
            "labeling_provider": self._provider,
            "labeling_model": self._labeling_model,
            "label_batch_size": self._label_batch_size,
            "label_concurrency": self._label_concurrency,
            "totals": {
                "reviews_input": n_input,
                "total_clusters": len(clusters),
                "micro_clusters": len(micro),
                "noise_points_before_fallback": n_noise_before,
                "noise_rate": round(n_noise_before / max(1, total_labels), 4),
                "avg_cluster_size": round(
                    sum(c.size for c in clusters) / max(1, len(clusters)), 1
                ),
                "largest_cluster_size": max((c.size for c in clusters), default=0),
            },
            "labeling_quality": {
                "avg_confidence": avg_conf,
                "below_threshold": len(needs_review),
                "confidence_threshold": 0.6,
            },
            "cluster_signals": {
                "discovery_related_clusters": len(discovery),
                "discovery_cluster_rate": round(len(discovery) / max(1, len(clusters)), 4),
                "trend_distribution": trend_dist,
            },
        }

    def _empty_report(self, date_str: str, run_start: datetime) -> dict:
        return {
            "phase": 4,
            "batch_id": self._batch_id,
            "run_date": run_start.isoformat(),
            "target_date": date_str,
            "duration_seconds": 0.0,
            "dry_run": self._dry_run,
            "totals": {},
            "note": f"No Phase 3 analyzed reviews found for date {date_str}",
        }

    def _write_report(self, report: dict) -> None:
        self._reports_dir.mkdir(parents=True, exist_ok=True)
        out = self._reports_dir / f"phase4_{self._batch_id}.json"
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("phase=4 event=report_written path=%s", out)


# ── CLI entry point ───────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 4 — Clustering & Pattern Recognition")
    parser.add_argument(
        "--phase3-dir",
        default=str(DEFAULT_PHASE3_DIR),
        help="Path to Phase 3 analyzed_reviews directory",
    )
    parser.add_argument(
        "--phase2-dir",
        default=str(DEFAULT_PHASE2_DIR),
        help="Path to Phase 2 normalized_reviews directory (for clean_text enrichment)",
    )
    parser.add_argument("--data-dir", default="data", help="Root data directory for output")
    parser.add_argument("--date", default=None, help="Process reviews from this date (YYYY-MM-DD)")
    parser.add_argument(
        "--provider",
        default="anthropic",
        choices=["anthropic", "groq", "ollama"],
        help="LLM provider for theme labeling (default: anthropic)",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="API key for the selected provider (or set ANTHROPIC_API_KEY / GROQ_API_KEY env var)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override the default model for the selected provider",
    )
    parser.add_argument(
        "--label-batch-size",
        type=int,
        default=10,
        help="Clusters per LLM call (default: 10). Higher = fewer calls, more tokens per call.",
    )
    parser.add_argument(
        "--label-concurrency",
        type=int,
        default=3,
        help="Concurrent LLM batch calls (default: 3). Higher = faster but more TPM pressure.",
    )
    parser.add_argument(
        "--skip-labeling", action="store_true", help="Skip LLM theme labeling (faster, for testing)"
    )
    parser.add_argument("--dry-run", action="store_true", help="Process but skip writing to disk")
    args = parser.parse_args()

    pipeline = ClusteringPipeline(
        phase3_dir=args.phase3_dir,
        phase2_dir=args.phase2_dir,
        data_dir=args.data_dir,
        provider=args.provider,
        api_key=args.api_key,
        labeling_model=args.model,
        label_batch_size=args.label_batch_size,
        label_concurrency=args.label_concurrency,
        dry_run=args.dry_run,
        skip_labeling=args.skip_labeling,
    )
    report = pipeline.run(date_str=args.date)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
