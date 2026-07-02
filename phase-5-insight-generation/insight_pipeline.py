"""Phase 5 — Insight Generation Pipeline

Orchestrates the full insight generation run:
  1. Load ReviewCluster[] from Phase 4
  2. Load AnalyzedReview[] from Phase 3 (for cross-reference)
  3. In parallel: JTBD inference + Segment profiling + Unmet need detection
  4. Cross-cluster JTBD synthesis (deterministic merge)
  5. Opportunity scoring (deterministic)
  6. Evidence mapping (deterministic)
  7. Rank insights
  8. Write all outputs to JSONL
  9. Emit quality report

Provider rotation for free-tier TPM
────────────────────────────────────
Pass --providers as a comma-separated ordered list. The first available
provider that is not in cooldown handles each LLM call. On rate limit,
the pipeline automatically rotates to the next provider.

Example invocations
───────────────────
# Single provider (default)
python insight_pipeline.py --providers anthropic

# Two-provider rotation (Anthropic primary, Groq fallback)
python insight_pipeline.py --providers anthropic,groq

# Full rotation with local Qwen fallback (ideal for free tiers)
python insight_pipeline.py --providers anthropic,groq,ollama --ollama-model qwen2.5:7b

# Groq-only with Qwen model
python insight_pipeline.py --providers groq --groq-model qwen-qwq-32b

# Local only (no API keys needed)
python insight_pipeline.py --providers ollama --ollama-model qwen2.5:14b

# Dry run — shows what would be processed without making LLM calls
python insight_pipeline.py --providers ollama --dry-run
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

# ── Path bootstrap ────────────────────────────────────────────────────────────
# Allow running this file directly from the phase-5 directory.
_PHASE5_ROOT = Path(__file__).parent
sys.path.insert(0, str(_PHASE5_ROOT))

from jtbd.cluster_jtbd_inferrer import ClusterJTBDInferrer
from jtbd.jtbd_synthesizer import JTBDSynthesizer
from llm.insight_llm_client import InsightLLMClient, PROVIDER_DEFAULTS
from opportunities.evidence_mapper import EvidenceMapper
from opportunities.opportunity_ranker import OpportunityRanker
from opportunities.opportunity_scorer import OpportunityScorer
from quality_report import build_quality_report
from schemas.product_insight import JTBDProfile, ProductInsight, UnmetNeed, UserSegment
from segments.segment_profiler import SegmentProfiler
from storage.insight_store import InsightStore
from unmet_needs.need_detector import UnmetNeedDetector
from unmet_needs.need_synthesizer import NeedSynthesizer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("insight_pipeline")

# Relative paths to sibling phase outputs
_PHASE2_DATA = _PHASE5_ROOT.parent / "phase-2-preprocessing" / "data" / "normalized_reviews"
_PHASE3_DATA = _PHASE5_ROOT.parent / "phase-3-ai-analysis" / "data" / "analyzed_reviews"
_PHASE4_DATA = _PHASE5_ROOT.parent / "phase-4-clustering" / "data" / "clusters"

# Phase 2 splits normalized reviews by platform — skip these non-data subdirs
_PHASE2_SKIP_DIRS = {"manifests", "excluded"}


# ── Data loading helpers ──────────────────────────────────────────────────────

def _find_latest_date_dir(base: Path) -> Optional[Path]:
    candidates = sorted(
        (d for d in base.iterdir() if d.is_dir() and d.name[:4].isdigit()),
        reverse=True,
    )
    return candidates[0] if candidates else None


def _load_jsonl_dir(directory: Path) -> list[dict]:
    records: list[dict] = []
    for path in sorted(directory.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    logger.warning("jsonl=parse_error path=%s error=%s", path.name, exc)
    return records


def load_clusters(date_str: Optional[str] = None) -> tuple[list[dict], str]:
    base = _PHASE4_DATA
    if date_str:
        date_dir = base / date_str
    else:
        date_dir = _find_latest_date_dir(base)
    if not date_dir or not date_dir.exists():
        logger.error("clusters=not_found base=%s date=%s", base, date_str)
        return [], ""
    clusters = _load_jsonl_dir(date_dir)
    logger.info("clusters=loaded count=%d date=%s", len(clusters), date_dir.name)
    return clusters, date_dir.name


def load_analyzed_reviews(date_str: Optional[str] = None) -> list[dict]:
    base = _PHASE3_DATA
    if date_str:
        date_dir = base / date_str
    else:
        date_dir = _find_latest_date_dir(base)
    if not date_dir or not date_dir.exists():
        logger.warning("analyzed_reviews=not_found base=%s — segment profiler will be limited", base)
        return []
    reviews = _load_jsonl_dir(date_dir)
    reviews = [r for r in reviews if r.get("analysis_status") != "failed"]
    logger.info("analyzed_reviews=loaded count=%d date=%s", len(reviews), date_dir.name)
    return reviews


def load_normalized_reviews(date_str: Optional[str] = None) -> list[dict]:
    """Load NormalizedReview records from Phase 2.

    Phase 2 stores normalized reviews split by platform:
      phase-2-preprocessing/data/normalized_reviews/{platform}/{date}/*.jsonl

    We walk every platform subdirectory (skipping 'manifests' and 'excluded')
    and collect all records for the target date.
    """
    base = _PHASE2_DATA
    if not base.exists():
        logger.warning("normalized_reviews=phase2_dir_not_found path=%s", base)
        return []

    records: list[dict] = []
    for platform_dir in sorted(base.iterdir()):
        if not platform_dir.is_dir() or platform_dir.name in _PHASE2_SKIP_DIRS:
            continue
        if date_str:
            date_dir = platform_dir / date_str
        else:
            date_dir = _find_latest_date_dir(platform_dir)
        if not date_dir or not date_dir.exists():
            continue
        platform_records = _load_jsonl_dir(date_dir)
        records.extend(platform_records)
        logger.debug(
            "normalized_reviews=loaded platform=%s count=%d", platform_dir.name, len(platform_records)
        )

    logger.info("normalized_reviews=loaded total=%d", len(records))
    return records


def build_review_text_lookup(
    analyzed_reviews: list[dict],
    normalized_reviews: list[dict],
) -> dict[str, str]:
    """Build {analyzed_review_id → clean_text} for evidence mapping and JTBD sampling.

    AnalyzedReview does NOT carry clean_text — it only stores extracted signals.
    clean_text lives in NormalizedReview (Phase 2).

    Join path:
      AnalyzedReview.normalized_review_id → NormalizedReview.id → clean_text
    """
    # Step 1: NormalizedReview.id → clean_text
    norm_text: dict[str, str] = {
        r["id"]: r["clean_text"]
        for r in normalized_reviews
        if r.get("id") and r.get("clean_text")
    }

    # Step 2: AnalyzedReview.id → clean_text via normalized_review_id
    lookup: dict[str, str] = {}
    missing = 0
    for ar in analyzed_reviews:
        aid = ar.get("id", "")
        nid = ar.get("normalized_review_id", "")
        text = norm_text.get(nid, "")
        if aid and text:
            lookup[aid] = text
        elif aid:
            missing += 1

    if missing:
        logger.warning(
            "review_text_lookup=missing_text count=%d "
            "(normalized_reviews not loaded or date mismatch)",
            missing,
        )
    logger.info("review_text_lookup=built size=%d", len(lookup))
    return lookup


# ── Provider config builder ───────────────────────────────────────────────────

def build_provider_configs(args: argparse.Namespace) -> list[dict]:
    """Convert CLI args into ordered provider config dicts."""
    providers_str = getattr(args, "providers", "anthropic")
    provider_list = [p.strip() for p in providers_str.split(",") if p.strip()]

    configs: list[dict] = []
    for provider in provider_list:
        if provider not in PROVIDER_DEFAULTS:
            logger.warning("provider=unknown name=%s skipping", provider)
            continue
        cfg: dict = {"provider": provider}

        if provider == "anthropic":
            if getattr(args, "anthropic_api_key", None):
                cfg["api_key"] = args.anthropic_api_key
            if getattr(args, "anthropic_model", None):
                cfg["model"] = args.anthropic_model

        elif provider == "groq":
            if getattr(args, "groq_api_key", None):
                cfg["api_key"] = args.groq_api_key
            if getattr(args, "groq_model", None):
                cfg["model"] = args.groq_model

        elif provider == "ollama":
            if getattr(args, "ollama_model", None):
                cfg["model"] = args.ollama_model
            if getattr(args, "ollama_base_url", None):
                # Inject custom base_url by patching PROVIDER_DEFAULTS temporarily
                PROVIDER_DEFAULTS["ollama"]["base_url"] = args.ollama_base_url

        configs.append(cfg)

    if not configs:
        raise ValueError("No valid providers specified. Use --providers anthropic|groq|ollama")
    return configs


# ── Pipeline ──────────────────────────────────────────────────────────────────

async def run_pipeline(
    clusters: list[dict],
    analyzed_reviews: list[dict],
    normalized_reviews: list[dict],
    provider_configs: list[dict],
    batch_id: str,
    date_str: str,
    concurrency: int = 3,
    batch_size: int = 5,
    dry_run: bool = False,
) -> dict:
    """Full Phase 5 pipeline. Returns the quality report dict."""

    total_reviews = len(analyzed_reviews) or sum(c.get("size", 0) for c in clusters)
    review_text_lookup = build_review_text_lookup(analyzed_reviews, normalized_reviews)

    eligible_clusters = [c for c in clusters if not c.get("is_micro_cluster")]
    logger.info(
        "pipeline=start total_clusters=%d eligible=%d total_reviews=%d",
        len(clusters), len(eligible_clusters), total_reviews,
    )

    if dry_run:
        logger.info("pipeline=dry_run skipping_all_llm_calls")
        return _dry_run_report(clusters, eligible_clusters, total_reviews, date_str, batch_id)

    # Determine provider name for prompt loading (first provider in list)
    primary_provider = provider_configs[0]["provider"]

    llm_client = InsightLLMClient(provider_configs)

    # ── Step 3: parallel analysis ─────────────────────────────────────────────
    logger.info("pipeline=step3 running_parallel_analysis")

    jtbd_inferrer = ClusterJTBDInferrer(
        llm_client, batch_size=batch_size, concurrency=concurrency,
        provider_name=primary_provider,
    )
    segment_profiler = SegmentProfiler(llm_client, provider_name=primary_provider)
    need_detector = UnmetNeedDetector()
    need_synthesizer = NeedSynthesizer(
        llm_client, batch_size=batch_size, concurrency=concurrency,
        provider_name=primary_provider,
    )

    # Detect unmet needs (CPU-only, run now before async tasks)
    raw_candidates = need_detector.detect(eligible_clusters, analyzed_reviews, review_text_lookup)
    logger.info("needs=detected raw_candidates=%d", len(raw_candidates))

    # Run JTBD inference + segment profiling + need synthesis concurrently
    jtbd_task = jtbd_inferrer.infer_all(eligible_clusters, review_text_lookup)
    segment_task = segment_profiler.profile_all(analyzed_reviews, total_reviews=total_reviews)
    need_task = need_synthesizer.synthesize_all(raw_candidates)

    jtbd_profiles_raw, user_segments, unmet_needs = await asyncio.gather(
        jtbd_task, segment_task, need_task
    )
    logger.info(
        "pipeline=parallel_done jtbd_raw=%d segments=%d unmet_needs=%d",
        len(jtbd_profiles_raw), len(user_segments), len(unmet_needs),
    )

    # ── Step 4: JTBD synthesis ────────────────────────────────────────────────
    logger.info("pipeline=step4 jtbd_synthesis")
    synthesizer = JTBDSynthesizer()
    jtbd_profiles: list[JTBDProfile] = synthesizer.merge(jtbd_profiles_raw)

    # Build cluster_id → jtbd short_label for scorer
    jtbd_cluster_map: dict[str, str] = {}
    for profile in jtbd_profiles:
        for cid in profile.supporting_cluster_ids:
            jtbd_cluster_map[cid] = profile.short_label

    # ── Step 5: Opportunity scoring ───────────────────────────────────────────
    logger.info("pipeline=step5 opportunity_scoring")
    scorer = OpportunityScorer()
    insights_unlinked: list[ProductInsight] = scorer.score_all(
        eligible_clusters,
        total_reviews=total_reviews,
        jtbd_cluster_map=jtbd_cluster_map,
        model_name=llm_client.primary_model,
        prompt_version="1.0",
    )

    # ── Step 6: Evidence mapping ──────────────────────────────────────────────
    logger.info("pipeline=step6 evidence_mapping")
    evidence_mapper = EvidenceMapper()
    insights: list[ProductInsight] = evidence_mapper.map_all(
        insights_unlinked, eligible_clusters, review_text_lookup
    )

    # ── Step 7: Rank ──────────────────────────────────────────────────────────
    logger.info("pipeline=step7 ranking")
    ranker = OpportunityRanker()
    ranked = ranker.rank(insights)

    # Also convert unmet_needs to ProductInsight records and append to pending
    unmet_insights = _unmet_needs_to_insights(
        unmet_needs, eligible_clusters, review_text_lookup, llm_client.primary_model
    )
    segment_insights = _segments_to_insights(user_segments, llm_client.primary_model)

    all_product_insights = ranked.all_ranked + unmet_insights + segment_insights

    # ── Step 8: Write ─────────────────────────────────────────────────────────
    logger.info("pipeline=step8 writing_outputs")
    store = InsightStore()
    store.write_product_insights(all_product_insights, batch_id, date_str)
    store.write_jtbd_profiles(jtbd_profiles, batch_id, date_str)
    store.write_user_segments(user_segments, batch_id, date_str)
    store.write_unmet_needs(unmet_needs, batch_id, date_str)

    # ── Step 9: Quality report ────────────────────────────────────────────────
    report = build_quality_report(
        run_date=datetime.now(timezone.utc).isoformat(),
        batch_id=batch_id,
        clusters=clusters,
        eligible_clusters=eligible_clusters,
        product_insights=all_product_insights,
        jtbd_profiles=jtbd_profiles,
        user_segments=user_segments,
        unmet_needs=unmet_needs,
        providers=[cfg["provider"] for cfg in provider_configs],
    )
    store.write_quality_report(report, batch_id)

    logger.info(
        "pipeline=complete insights=%d jtbd=%d segments=%d needs=%d",
        len(all_product_insights), len(jtbd_profiles), len(user_segments), len(unmet_needs),
    )
    return report


# ── Conversion helpers ────────────────────────────────────────────────────────

def _unmet_needs_to_insights(
    needs: list[UnmetNeed],
    clusters: list[dict],
    review_lookup: dict[str, str],
    model: str,
) -> list[ProductInsight]:
    """Wrap UnmetNeed records as ProductInsight for unified storage."""
    cluster_map = {c["id"]: c for c in clusters}
    evidence_mapper = EvidenceMapper()
    now = datetime.now(timezone.utc).isoformat()
    insights: list[ProductInsight] = []

    for need in needs:
        cluster = cluster_map.get(need.supporting_cluster_ids[0], {}) if need.supporting_cluster_ids else {}
        review_ids, verbatims = evidence_mapper._pick_evidence(
            need.supporting_cluster_ids, cluster_map, review_lookup
        )
        size = cluster.get("size", need.expressed_frequency)
        total_reviews = max(size, 1)
        freq = min(need.expressed_frequency / total_reviews, 1.0)

        insights.append(
            ProductInsight(
                id=str(uuid.uuid4()),
                title=need.need_statement[:120],
                description=need.gap_description,
                insight_type="unmet_need",
                supporting_cluster_ids=need.supporting_cluster_ids,
                supporting_review_ids=review_ids,
                supporting_verbatims=verbatims,
                affected_segment=need.affected_segment,
                frequency_score=round(freq, 4),
                severity_score=round(min(need.expressed_frequency / 100, 1.0), 4),
                uniqueness_score=0.5,
                opportunity_score=round(freq * 0.4 + 0.5 * 0.4 + 0.5 * 0.2, 4),
                confidence="medium" if need.confidence_score >= 0.5 else "low",
                confidence_score=need.confidence_score,
                reasoning=f"Detected via linguistic patterns: {', '.join(need.linguistic_patterns_matched)}.",
                discovery_friction_related=cluster.get("is_discovery_related", False),
                trend_direction=cluster.get("trend_direction", "stable"),
                review_required=need.confidence_score < 0.6,
                generated_at=now,
                generation_model=model,
                prompt_version=need.prompt_version,
            )
        )
    return insights


def _segments_to_insights(
    segments: list[UserSegment], model: str
) -> list[ProductInsight]:
    """Wrap UserSegment records as ProductInsight for unified storage."""
    now = datetime.now(timezone.utc).isoformat()
    insights: list[ProductInsight] = []

    for seg in segments:
        insights.append(
            ProductInsight(
                id=str(uuid.uuid4()),
                title=f"{seg.segment_label.replace('_', ' ').title()} Segment: {seg.primary_pain[:80]}",
                description=seg.description,
                insight_type="segment",
                supporting_cluster_ids=[],
                supporting_review_ids=[],
                supporting_verbatims=[],
                affected_segment=seg.segment_label,
                frequency_score=round(seg.fraction_of_total, 4),
                severity_score=round(max(0.0, -seg.avg_sentiment_score), 4),
                uniqueness_score=round(1.0 - seg.fraction_of_total, 4),
                opportunity_score=round(
                    seg.fraction_of_total * 0.4
                    + max(0.0, -seg.avg_sentiment_score) * 0.4
                    + (1.0 - seg.fraction_of_total) * 0.2,
                    4,
                ),
                confidence="high",
                confidence_score=0.8,
                reasoning=seg.primary_jtbd,
                discovery_friction_related=seg.discovery_friction_rate > 0.3,
                trend_direction="stable",
                review_required=False,
                generated_at=now,
                generation_model=model,
                prompt_version="1.0",
            )
        )
    return insights


def _dry_run_report(clusters, eligible, total_reviews, date_str, batch_id) -> dict:
    return {
        "run_date": datetime.now(timezone.utc).isoformat(),
        "batch_id": batch_id,
        "date_str": date_str,
        "dry_run": True,
        "total_clusters": len(clusters),
        "eligible_clusters": len(eligible),
        "total_reviews": total_reviews,
        "estimated_llm_calls": {
            "jtbd_batches": (len(eligible) + 4) // 5,
            "segment_calls": 5,
            "need_batches": "depends on pattern detection results",
        },
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Phase 5 Insight Generation Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--providers",
        default="anthropic",
        help="Comma-separated ordered provider list: anthropic,groq,ollama "
             "(default: anthropic). First available provider handles each call; "
             "falls back to next on rate limit.",
    )
    p.add_argument("--anthropic-api-key", help="Anthropic API key (overrides env ANTHROPIC_API_KEY)")
    p.add_argument("--anthropic-model", default=None, help="Anthropic model override")
    p.add_argument("--groq-api-key", help="Groq API key (overrides env GROQ_API_KEY)")
    p.add_argument(
        "--groq-model",
        default=None,
        help="Groq model (e.g. llama-3.3-70b-versatile, qwen-qwq-32b)",
    )
    p.add_argument(
        "--ollama-model",
        default=None,
        help="Ollama model (e.g. llama3.1, qwen2.5:7b, qwen2.5:14b, qwen3:8b)",
    )
    p.add_argument(
        "--ollama-base-url",
        default=None,
        help="Custom Ollama base URL (default: http://localhost:11434/v1)",
    )
    p.add_argument("--date", default=None, help="YYYY-MM-DD date to process (default: latest)")
    p.add_argument("--concurrency", type=int, default=3, help="Max concurrent LLM calls (default: 3)")
    p.add_argument("--batch-size", type=int, default=5, help="Clusters per LLM call (default: 5)")
    p.add_argument("--dry-run", action="store_true", help="Estimate work without making LLM calls")
    p.add_argument("--verbose", action="store_true", help="Enable DEBUG logging")
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    batch_id = str(uuid.uuid4())[:8]
    logger.info("pipeline=init batch_id=%s providers=%s", batch_id, args.providers)

    # Load input data
    clusters, cluster_date = load_clusters(args.date)
    if not clusters:
        logger.error("pipeline=abort reason=no_clusters_found")
        return 1

    date_str = args.date or cluster_date
    analyzed_reviews = load_analyzed_reviews(date_str)
    normalized_reviews = load_normalized_reviews(date_str)

    # Build provider configs from CLI
    try:
        provider_configs = build_provider_configs(args)
    except ValueError as exc:
        logger.error("provider_config_error=%s", exc)
        return 1

    logger.info(
        "pipeline=configured providers=%s batch_id=%s date=%s concurrency=%d batch_size=%d",
        [c["provider"] for c in provider_configs], batch_id, date_str,
        args.concurrency, args.batch_size,
    )

    report = asyncio.run(
        run_pipeline(
            clusters=clusters,
            analyzed_reviews=analyzed_reviews,
            normalized_reviews=normalized_reviews,
            provider_configs=provider_configs,
            batch_id=batch_id,
            date_str=date_str,
            concurrency=args.concurrency,
            batch_size=args.batch_size,
            dry_run=args.dry_run,
        )
    )

    # Print summary (ASCII only — safe on all terminal encodings)
    sep = "-" * 54
    print(f"\n{sep}")
    print("Phase 5 Complete")
    print(sep)
    if args.dry_run:
        print("DRY RUN -- no LLM calls made")
        print(json.dumps(report, indent=2))
    else:
        gen = report.get("insights_generated", {})
        print(f"  Product insights : {gen.get('product_insights', 0)}")
        print(f"  JTBD profiles    : {gen.get('jtbd_profiles', 0)}")
        print(f"  User segments    : {gen.get('user_segments', 0)}")
        print(f"  Unmet needs      : {gen.get('unmet_needs', 0)}")
        print(f"  Top opp score    : {report.get('top_opportunity_score', 0):.3f}")
        print(f"  Avg confidence   : {report.get('avg_confidence_score', 0):.3f}")
        print(f"  Pending review   : {report.get('low_confidence_insights', 0)}")
    print(f"{sep}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
