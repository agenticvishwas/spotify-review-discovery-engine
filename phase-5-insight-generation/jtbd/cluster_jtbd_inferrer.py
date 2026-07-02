"""Per-cluster JTBD inference with batched LLM calls.

Batching strategy
─────────────────
Groups clusters into batches of `batch_size` (default 5) and issues a single
LLM call per batch. At 200 clusters with batch_size=5 this means 40 LLM calls
instead of 200 — a 5× TPM reduction that is critical on free-tier keys.

Async concurrency
─────────────────
Batches are processed concurrently up to `concurrency` (default 3). The
semaphore ensures we never exceed the provider's request concurrency limit.

Resume safety
─────────────
Already-inferred cluster IDs (passed as `skip_cluster_ids`) are skipped so
that re-runs after partial failures don't re-process completed clusters.
"""

import asyncio
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from llm.insight_llm_client import InsightLLMClient, InsightLLMError
from schemas.product_insight import JTBDProfile

logger = logging.getLogger(__name__)

_PROMPT_DIR = Path(__file__).parent / "prompts"
CURRENT_PROMPT_VERSION = "1.0"
_DEFAULT_BATCH_SIZE = 5
_DEFAULT_CONCURRENCY = 3

JTBD_PATTERN = re.compile(
    r"when\s+.+,\s*i\s+want\s+to\s+.+,\s*so\s+i\s+can\s+",
    re.IGNORECASE,
)


def _load_prompt(version: str, provider: str) -> dict:
    specific = _PROMPT_DIR / f"jtbd_inference_v{version}_{provider}.json"
    if specific.exists():
        return json.loads(specific.read_text(encoding="utf-8"))
    generic = _PROMPT_DIR / f"jtbd_inference_v{version}.json"
    return json.loads(generic.read_text(encoding="utf-8"))


def _build_clusters_block(clusters: list[dict], review_lookup: dict[str, str]) -> str:
    """Format a batch of clusters into a compact text block for the prompt."""
    sections: list[str] = []
    for i, cluster in enumerate(clusters, 1):
        theme = cluster.get("theme", cluster.get("label", ""))
        label = cluster.get("label", "")
        size = cluster.get("size", 0)
        avg_sentiment = cluster.get("avg_sentiment_score", 0.0)
        friction_rate = cluster.get("discovery_friction_rate", 0.0)
        trend = cluster.get("trend_direction", "stable")
        emotion = cluster.get("dominant_emotion", "unknown")
        features = ", ".join(cluster.get("top_features_mentioned", [])[:5]) or "none"

        # Pull up to 5 representative review texts
        rep_ids = cluster.get("representative_review_ids", [])[:5]
        review_lines: list[str] = []
        for rid in rep_ids:
            text = review_lookup.get(rid, "")
            if text:
                review_lines.append(f'  - "{text[:200]}"')

        reviews_block = "\n".join(review_lines) if review_lines else "  (no sample reviews)"

        sections.append(
            f"[CLUSTER {i}]\n"
            f"Label: {label}\n"
            f"Theme: {theme}\n"
            f"Size: {size} reviews | Sentiment avg: {avg_sentiment:.2f} | "
            f"Friction rate: {friction_rate:.0%} | Trend: {trend} | "
            f"Dominant emotion: {emotion}\n"
            f"Features mentioned: {features}\n"
            f"Sample reviews:\n{reviews_block}"
        )
    return "\n\n".join(sections)


def _validate_job_statement(statement: str) -> bool:
    return bool(JTBD_PATTERN.search(statement))


def _fix_job_statement(statement: str) -> str:
    """Best-effort normalisation if the LLM omitted When/I want/so I can."""
    s = statement.strip().rstrip(".")
    if not s.lower().startswith("when "):
        s = "When using Spotify, " + s[0].lower() + s[1:]
    return s


class ClusterJTBDInferrer:
    """Infers one JTBDProfile per cluster using batched, concurrent LLM calls."""

    def __init__(
        self,
        llm_client: InsightLLMClient,
        batch_size: int = _DEFAULT_BATCH_SIZE,
        concurrency: int = _DEFAULT_CONCURRENCY,
        prompt_version: str = CURRENT_PROMPT_VERSION,
        provider_name: str = "anthropic",
    ):
        self._client = llm_client
        self._batch_size = batch_size
        self._concurrency = concurrency
        self._prompt_cfg = _load_prompt(prompt_version, provider_name)
        self._prompt_version = prompt_version

    async def infer_all(
        self,
        clusters: list[dict],
        review_lookup: dict[str, str],
        skip_cluster_ids: Optional[set[str]] = None,
    ) -> list[JTBDProfile]:
        """Infer JTBDs for all eligible clusters.

        Args:
            clusters: list of ReviewCluster dicts (from Phase 4 JSONL)
            review_lookup: {review_id → clean_text} for sampling verbatims
            skip_cluster_ids: cluster IDs already processed (resume support)

        Returns:
            list of JTBDProfile objects, one per eligible cluster
        """
        skip = skip_cluster_ids or set()
        eligible = [c for c in clusters if not c.get("is_micro_cluster") and c["id"] not in skip]

        if not eligible:
            logger.info("jtbd=no_eligible_clusters total=%d skipped=%d", len(clusters), len(skip))
            return []

        batches = [
            eligible[i : i + self._batch_size]
            for i in range(0, len(eligible), self._batch_size)
        ]
        logger.info(
            "jtbd=starting clusters=%d batches=%d concurrency=%d batch_size=%d",
            len(eligible), len(batches), self._concurrency, self._batch_size,
        )

        semaphore = asyncio.Semaphore(self._concurrency)
        tasks = [
            self._process_batch_safe(batch, review_lookup, semaphore, batch_idx, len(batches))
            for batch_idx, batch in enumerate(batches, 1)
        ]
        batch_results = await asyncio.gather(*tasks)

        profiles: list[JTBDProfile] = []
        for group in batch_results:
            profiles.extend(group)

        logger.info("jtbd=complete profiles=%d", len(profiles))
        return profiles

    async def _process_batch_safe(
        self,
        batch: list[dict],
        review_lookup: dict[str, str],
        semaphore: asyncio.Semaphore,
        batch_idx: int,
        total_batches: int,
    ) -> list[JTBDProfile]:
        async with semaphore:
            try:
                profiles = await self._process_batch(batch, review_lookup)
                logger.info("jtbd=batch_done %d/%d profiles=%d", batch_idx, total_batches, len(profiles))
                return profiles
            except InsightLLMError as exc:
                logger.error("jtbd=batch_failed %d/%d error=%s", batch_idx, total_batches, exc)
                return self._fallback_profiles(batch)

    async def _process_batch(
        self, batch: list[dict], review_lookup: dict[str, str]
    ) -> list[JTBDProfile]:
        clusters_block = _build_clusters_block(batch, review_lookup)
        user_message = self._prompt_cfg["user_template"].format(
            batch_size=len(batch),
            clusters_block=clusters_block,
        )
        result, tokens, model = await self._client.call(
            system=self._prompt_cfg["system"],
            user_message=user_message,
            max_tokens=self._prompt_cfg["max_tokens"],
            temperature=self._prompt_cfg["temperature"],
        )

        raw_results = result.get("results", [])
        profiles: list[JTBDProfile] = []
        now = datetime.now(timezone.utc).isoformat()

        for raw in raw_results:
            idx = raw.get("cluster_index", 1) - 1
            if idx < 0 or idx >= len(batch):
                continue
            cluster = batch[idx]
            job_stmt = raw.get("job_statement", "")
            if not _validate_job_statement(job_stmt):
                job_stmt = _fix_job_statement(job_stmt)

            sat = float(raw.get("satisfaction_score", 0.5))
            sat = max(0.0, min(1.0, sat))
            conf = float(raw.get("confidence", 0.6))
            conf = max(0.0, min(1.0, conf))

            profiles.append(
                JTBDProfile(
                    id=str(uuid.uuid4()),
                    job_statement=job_stmt,
                    short_label=raw.get("short_label", cluster.get("label", ""))[:80],
                    supporting_cluster_ids=[cluster["id"]],
                    user_segments=_infer_segments(cluster),
                    frequency_estimate=cluster.get("size", 0),
                    satisfaction_score=round(sat, 4),
                    gap_score=round(1.0 - sat, 4),
                    confidence_score=round(conf, 4),
                    gap_description=raw.get("gap_description", ""),
                    generated_at=now,
                    generation_model=model,
                    prompt_version=self._prompt_version,
                )
            )
        return profiles

    def _fallback_profiles(self, batch: list[dict]) -> list[JTBDProfile]:
        """Return minimal placeholder profiles when the LLM call fails."""
        now = datetime.now(timezone.utc).isoformat()
        return [
            JTBDProfile(
                id=str(uuid.uuid4()),
                job_statement=(
                    f"When using Spotify, I want to {cluster.get('label', 'accomplish my goal')}, "
                    f"so I can get better value from the product."
                ),
                short_label=cluster.get("label", "unknown")[:80],
                supporting_cluster_ids=[cluster["id"]],
                user_segments=_infer_segments(cluster),
                frequency_estimate=cluster.get("size", 0),
                satisfaction_score=0.5,
                gap_score=0.5,
                confidence_score=0.1,
                gap_description="LLM inference failed — manual review required.",
                generated_at=now,
                generation_model="fallback",
                prompt_version=self._prompt_version,
            )
            for cluster in batch
        ]


def _infer_segments(cluster: dict) -> list[str]:
    """Derive likely user segments from cluster metadata without an LLM call."""
    segments: list[str] = []
    # Use dominant_emotion and sentiment as proxies
    emotion = cluster.get("dominant_emotion", "")
    sentiment = cluster.get("avg_sentiment_score", 0.0)
    friction = cluster.get("discovery_friction_rate", 0.0)

    if sentiment > 0.3:
        segments.append("casual")
    if sentiment < -0.3 and friction > 0.5:
        segments.append("power_user")
    if emotion in ("frustration", "disappointment"):
        if "churned" not in segments:
            segments.append("churned")
    if not segments:
        segments.append("all")
    return segments
