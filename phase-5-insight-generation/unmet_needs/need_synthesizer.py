"""LLM-powered unmet need statement synthesis.

Takes RawNeedCandidates from the detector and formulates canonical
"Users need X but currently cannot Y" statements via batched LLM calls.

Batching: 5 candidates per LLM call (same strategy as JTBD inferrer).
"""

import asyncio
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from llm.insight_llm_client import InsightLLMClient, InsightLLMError
from schemas.product_insight import UnmetNeed
from unmet_needs.need_detector import RawNeedCandidate

logger = logging.getLogger(__name__)

_PROMPT_DIR = Path(__file__).parent / "prompts"
CURRENT_PROMPT_VERSION = "1.0"
_DEFAULT_BATCH_SIZE = 5
_DEFAULT_CONCURRENCY = 3

_NEED_PATTERN = re.compile(
    r"users?\s+need\s+.+\s+but\s+(currently\s+)?cannot\s+",
    re.IGNORECASE,
)


def _load_prompt(version: str, provider: str) -> dict:
    specific = _PROMPT_DIR / f"need_synthesis_v{version}_{provider}.json"
    if specific.exists():
        return json.loads(specific.read_text(encoding="utf-8"))
    generic = _PROMPT_DIR / f"need_synthesis_v{version}.json"
    return json.loads(generic.read_text(encoding="utf-8"))


def _build_needs_block(candidates: list[RawNeedCandidate]) -> str:
    sections: list[str] = []
    for i, c in enumerate(candidates, 1):
        reviews_block = "\n".join(
            f'  - "{t[:200]}"' for t in c.sample_texts[:5]
        ) or "  (no samples)"
        sections.append(
            f"[NEED GROUP {i}]\n"
            f"Cluster: {c.cluster_label}\n"
            f"Theme: {c.cluster_theme}\n"
            f"Frequency: {c.expressed_frequency} reviews\n"
            f"Affected segment: {c.affected_segment}\n"
            f"Patterns found: {', '.join(c.matched_patterns)}\n"
            f"Sample reviews:\n{reviews_block}"
        )
    return "\n\n".join(sections)


def _fix_need_statement(statement: str) -> str:
    s = statement.strip()
    if not s.lower().startswith("user"):
        s = "Users need " + s[0].lower() + s[1:]
    return s


class NeedSynthesizer:
    """Synthesises UnmetNeed records from RawNeedCandidates using batched LLM calls."""

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

    async def synthesize_all(
        self, candidates: list[RawNeedCandidate]
    ) -> list[UnmetNeed]:
        if not candidates:
            return []

        batches = [
            candidates[i : i + self._batch_size]
            for i in range(0, len(candidates), self._batch_size)
        ]
        logger.info(
            "needs=synthesizing candidates=%d batches=%d batch_size=%d",
            len(candidates), len(batches), self._batch_size,
        )

        semaphore = asyncio.Semaphore(self._concurrency)
        tasks = [
            self._process_batch_safe(batch, semaphore, idx, len(batches))
            for idx, batch in enumerate(batches, 1)
        ]
        batch_results = await asyncio.gather(*tasks)

        needs: list[UnmetNeed] = []
        for group in batch_results:
            needs.extend(group)

        logger.info("needs=complete count=%d", len(needs))
        return needs

    async def _process_batch_safe(
        self,
        batch: list[RawNeedCandidate],
        semaphore: asyncio.Semaphore,
        batch_idx: int,
        total_batches: int,
    ) -> list[UnmetNeed]:
        async with semaphore:
            try:
                return await self._process_batch(batch)
            except InsightLLMError as exc:
                logger.error(
                    "needs=batch_failed %d/%d error=%s", batch_idx, total_batches, exc
                )
                return self._fallback_needs(batch)

    async def _process_batch(self, batch: list[RawNeedCandidate]) -> list[UnmetNeed]:
        needs_block = _build_needs_block(batch)
        prompt_cfg = self._prompt_cfg
        user_message = prompt_cfg["user_template"].format(
            batch_size=len(batch),
            needs_block=needs_block,
        )
        result, _, model = await self._client.call(
            system=prompt_cfg["system"],
            user_message=user_message,
            max_tokens=prompt_cfg["max_tokens"],
            temperature=prompt_cfg["temperature"],
        )

        raw_results = result.get("results", [])
        needs: list[UnmetNeed] = []
        now = datetime.now(timezone.utc).isoformat()

        for raw in raw_results:
            idx = raw.get("need_index", 1) - 1
            if idx < 0 or idx >= len(batch):
                continue
            candidate = batch[idx]
            stmt = raw.get("need_statement", "")
            if not _NEED_PATTERN.search(stmt):
                stmt = _fix_need_statement(stmt)

            conf = float(raw.get("confidence", 0.5))
            conf = max(0.0, min(1.0, conf))

            needs.append(
                UnmetNeed(
                    id=str(uuid.uuid4()),
                    need_statement=stmt,
                    supporting_cluster_ids=[candidate.cluster_id],
                    affected_segment=candidate.affected_segment,
                    expressed_frequency=candidate.expressed_frequency,
                    related_features=raw.get("related_features", [])[:10],
                    gap_description=raw.get("gap_description", ""),
                    confidence_score=round(conf, 4),
                    linguistic_patterns_matched=candidate.matched_patterns,
                    generated_at=now,
                    generation_model=model,
                    prompt_version=self._prompt_version,
                )
            )
        return needs

    def _fallback_needs(self, batch: list[RawNeedCandidate]) -> list[UnmetNeed]:
        now = datetime.now(timezone.utc).isoformat()
        return [
            UnmetNeed(
                id=str(uuid.uuid4()),
                need_statement=(
                    f"Users need better {c.cluster_label or 'functionality'} "
                    f"but currently cannot achieve their goal seamlessly."
                ),
                supporting_cluster_ids=[c.cluster_id],
                affected_segment=c.affected_segment,
                expressed_frequency=c.expressed_frequency,
                related_features=[],
                gap_description="LLM synthesis failed — manual review required.",
                confidence_score=0.1,
                linguistic_patterns_matched=c.matched_patterns,
                generated_at=now,
                generation_model="fallback",
                prompt_version=self._prompt_version,
            )
            for c in batch
        ]
