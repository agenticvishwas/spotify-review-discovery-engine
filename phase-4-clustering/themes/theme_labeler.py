"""LLM-assisted cluster theme labeling — supports Anthropic, Groq, and Ollama.

Performance design
------------------
- Batch mode: packs `batch_size` clusters into a single LLM call (default 10)
- Concurrent: runs `concurrency` batches in parallel via ThreadPoolExecutor (default 3)
- Text truncation: review text capped at MAX_CHARS_PER_REVIEW before sending
- Micro-cluster bypass: clusters flagged is_micro_cluster=True are auto-labelled;
  no LLM call needed
- Fallback: if a batch call or parse fails, each cluster in that batch is retried
  individually so no data is lost

Provider     Key source              Default model
-----------  ----------------------  --------------------------
anthropic    ANTHROPIC_API_KEY       claude-sonnet-4-6
groq         GROQ_API_KEY            llama-3.3-70b-versatile
ollama       no key required         llama3.1 (local)
"""

import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

LABELING_PROMPT_VERSION = "1.0"       # single-cluster prompt (fallback)
LABELING_BATCH_PROMPT_VERSION = "2.0"  # multi-cluster batch prompt
LOW_CONFIDENCE_THRESHOLD = 0.6
GENERIC_LABELS = frozenset({"mixed feedback", "general feedback", "various issues", "miscellaneous"})
MAX_CHARS_PER_REVIEW = 200   # truncate before sending to reduce token cost
REVIEWS_PER_CLUSTER_IN_BATCH = 3  # fewer per cluster keeps batch prompts short

_SINGLE_PROMPT_PATH = Path(__file__).parent / "prompts" / "cluster_labeling_v1.0.md"

PROVIDER_DEFAULTS: dict[str, dict] = {
    "anthropic": {
        "model": "claude-sonnet-4-6",
        "base_url": None,
        "env_key": "ANTHROPIC_API_KEY",
        "requires_key": True,
    },
    "groq": {
        "model": "llama-3.3-70b-versatile",
        "base_url": "https://api.groq.com/openai/v1",
        "env_key": "GROQ_API_KEY",
        "requires_key": True,
    },
    "ollama": {
        "model": "llama3.1",
        "base_url": "http://localhost:11434/v1",
        "env_key": None,
        "requires_key": False,
    },
}


class ThemeLabeler:
    """Labels each cluster with a short name, one-sentence theme, and discovery flag.

    Call label_all() — it automatically batches, parallelises, and falls back.
    """

    def __init__(
        self,
        provider: str = "anthropic",
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        if provider not in PROVIDER_DEFAULTS:
            raise ValueError(
                f"Unknown provider '{provider}'. Choose from: {list(PROVIDER_DEFAULTS)}"
            )

        cfg = PROVIDER_DEFAULTS[provider]
        self._provider = provider
        self._single_prompt_template = _SINGLE_PROMPT_PATH.read_text(encoding="utf-8")
        self._model = model or cfg["model"]

        resolved_key = api_key or (os.environ.get(cfg["env_key"]) if cfg["env_key"] else None)
        if cfg["requires_key"] and not resolved_key:
            raise EnvironmentError(
                f"Provider '{provider}' requires an API key. "
                f"Set {cfg['env_key']} or pass --api-key."
            )

        if provider == "anthropic":
            import anthropic
            self._client = anthropic.Anthropic(api_key=resolved_key)
        else:
            import openai
            self._client = openai.OpenAI(
                api_key=resolved_key or "ollama",
                base_url=cfg["base_url"],
            )

        logger.info(
            "phase=4 action=labeler_init provider=%s model=%s",
            self._provider, self._model,
        )

    @property
    def model(self) -> str:
        return self._model

    @property
    def provider(self) -> str:
        return self._provider

    # ── Public entry point ────────────────────────────────────────────────────

    def label_all(
        self,
        clusters: list[dict],
        review_text_lookup: dict[str, str],
        batch_size: int = 10,
        concurrency: int = 3,
    ) -> list[dict]:
        """Label all clusters using batched, concurrent LLM calls.

        Micro-clusters are auto-labelled without any API call.
        If a batch fails to parse, each cluster in it is retried individually.
        """
        t0 = time.monotonic()
        result_map: dict[str, dict] = {}  # cluster id → merged dict

        # ── 1. Auto-label micro-clusters (no LLM) ───────────────────────────
        micro = [c for c in clusters if c.get("is_micro_cluster", False)]
        regular = [c for c in clusters if not c.get("is_micro_cluster", False)]

        for c in micro:
            result_map[c["id"]] = {**c, **self._auto_label_micro()}

        if micro:
            logger.info("phase=4 action=micro_auto_labelled count=%d", len(micro))

        # ── 2. Split regular clusters into batches ───────────────────────────
        batches = [regular[i : i + batch_size] for i in range(0, len(regular), batch_size)]
        logger.info(
            "phase=4 action=label_start regular=%d batches=%d concurrency=%d",
            len(regular), len(batches), concurrency,
        )

        # ── 3. Run batches concurrently ──────────────────────────────────────
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            future_to_batch = {
                pool.submit(self._label_batch_safe, batch, review_text_lookup, i + 1, len(batches)): batch
                for i, batch in enumerate(batches)
            }
            for future in as_completed(future_to_batch):
                batch = future_to_batch[future]
                batch_results = future.result()  # _label_batch_safe never raises
                for cluster, label_result in zip(batch, batch_results):
                    result_map[cluster["id"]] = {**cluster, **label_result}

        # ── 4. Restore original order ────────────────────────────────────────
        labeled = [result_map[c["id"]] for c in clusters]

        elapsed = time.monotonic() - t0
        n_review = sum(1 for c in labeled if c.get("review_required", False))
        avg_conf = sum(c.get("labeling_confidence", 0) for c in labeled) / max(1, len(labeled))
        logger.info(
            "phase=4 action=label_complete provider=%s model=%s clusters=%d "
            "elapsed_s=%.1f avg_confidence=%.3f needs_review=%d",
            self._provider, self._model, len(labeled), elapsed, avg_conf, n_review,
        )
        return labeled

    # ── Batch execution ───────────────────────────────────────────────────────

    def _label_batch_safe(
        self,
        batch: list[dict],
        review_text_lookup: dict[str, str],
        batch_num: int,
        total_batches: int,
    ) -> list[dict]:
        """Wraps _label_batch; on any failure falls back to per-cluster labeling."""
        try:
            results = self._label_batch(batch, review_text_lookup, batch_num, total_batches)
            if len(results) == len(batch):
                return results
            logger.warning(
                "phase=4 action=batch_count_mismatch batch=%d/%d expected=%d got=%d — falling back",
                batch_num, total_batches, len(batch), len(results),
            )
        except Exception as exc:
            logger.warning(
                "phase=4 action=batch_failed batch=%d/%d error=%s — falling back to per-cluster",
                batch_num, total_batches, exc,
            )

        # Fallback: label each cluster individually
        return [self._label_single(self._get_review_texts(c, review_text_lookup)) for c in batch]

    def _label_batch(
        self,
        batch: list[dict],
        review_text_lookup: dict[str, str],
        batch_num: int,
        total_batches: int,
    ) -> list[dict]:
        """Send one LLM call for the entire batch; parse array response."""
        prompt = self._build_batch_prompt(batch, review_text_lookup)
        max_tokens = min(200 * len(batch), 4096)

        raw = self._call_provider(prompt, max_tokens=max_tokens)
        parsed = self._parse_json(raw)

        # Response is wrapped: {"clusters": [...]}
        items: list[dict] = parsed.get("clusters", parsed) if isinstance(parsed, dict) else parsed

        results = []
        for i, cluster in enumerate(batch):
            item = items[i] if i < len(items) else {}
            results.append(self._extract_label_fields(item, version=LABELING_BATCH_PROMPT_VERSION))

        logger.debug(
            "phase=4 action=batch_complete batch=%d/%d size=%d",
            batch_num, total_batches, len(batch),
        )
        return results

    # ── Prompt builders ───────────────────────────────────────────────────────

    def _build_batch_prompt(self, batch: list[dict], review_text_lookup: dict[str, str]) -> str:
        sections = []
        for i, cluster in enumerate(batch, 1):
            texts = self._get_review_texts(cluster, review_text_lookup, n=REVIEWS_PER_CLUSTER_IN_BATCH)
            review_lines = "\n".join(f"  Review {j+1}: {t}" for j, t in enumerate(texts))
            sections.append(f"[CLUSTER {i}]\n{review_lines}")

        clusters_block = "\n\n".join(sections)
        return (
            "You are a product research analyst for a music streaming app.\n"
            "Label each review cluster below.\n\n"
            f"{clusters_block}\n\n"
            f"Return a JSON object with a 'clusters' array — one item per cluster, in order:\n"
            '{"clusters": [\n'
            '  {"cluster_index": 1, "label": "3-5 word label", '
            '"theme": "one sentence", "is_discovery_related": true, "confidence": 0.85},\n'
            "  ...\n"
            "]}\n\n"
            "is_discovery_related: true only if the cluster is about music discovery, "
            "recommendations, or finding new content.\n"
            "confidence: 0.0 (totally mixed reviews) to 1.0 (perfectly unified theme).\n"
            "Return only the JSON object, no other text."
        )

    def _build_single_prompt(self, review_texts: list[str]) -> str:
        padded = (review_texts + ["(no review available)"] * 5)[:5]
        prompt = self._single_prompt_template
        for i, text in enumerate(padded):
            prompt = prompt.replace(f"{{review_{i+1}}}", text)
        return prompt

    # ── Per-cluster fallback ──────────────────────────────────────────────────

    def _label_single(self, review_texts: list[str]) -> dict:
        prompt = self._build_single_prompt(review_texts)
        try:
            raw = self._call_provider(prompt, max_tokens=256)
            data = self._parse_json(raw)
            return self._extract_label_fields(data, version=LABELING_PROMPT_VERSION)
        except Exception as exc:
            logger.warning(
                "phase=4 action=single_label_failed provider=%s error=%s", self._provider, exc
            )
            return self._fallback_label()

    # ── Provider dispatch ─────────────────────────────────────────────────────

    def _call_provider(self, prompt: str, max_tokens: int = 256) -> str:
        if self._provider == "anthropic":
            return self._call_anthropic(prompt, max_tokens)
        elif self._provider == "ollama":
            return self._call_ollama(prompt, max_tokens)
        else:
            return self._call_openai_compat(prompt, max_tokens)

    def _call_anthropic(self, prompt: str, max_tokens: int) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()

    def _call_openai_compat(self, prompt: str, max_tokens: int) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content or ""

    def _call_ollama(self, prompt: str, max_tokens: int) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content or ""

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_review_texts(
        self,
        cluster: dict,
        review_text_lookup: dict[str, str],
        n: int = 5,
    ) -> list[str]:
        rep_ids = cluster.get("representative_review_ids", [])[:n]
        texts = [review_text_lookup.get(rid, "")[:MAX_CHARS_PER_REVIEW] for rid in rep_ids]
        return [t for t in texts if t.strip()]

    def _extract_label_fields(self, data: dict, version: str) -> dict:
        label = str(data.get("label", "Unlabeled Cluster")).strip()
        confidence = float(data.get("confidence", 0.5))
        is_generic = label.lower() in GENERIC_LABELS
        return {
            "label": label,
            "theme": str(data.get("theme", "")).strip(),
            "is_discovery_related": bool(data.get("is_discovery_related", False)),
            "labeling_confidence": confidence,
            "review_required": confidence < LOW_CONFIDENCE_THRESHOLD or is_generic,
            "labeling_model": self._model,
            "labeling_prompt_version": version,
        }

    def _auto_label_micro(self) -> dict:
        return {
            "label": "Small Cluster",
            "theme": "Cluster too small for reliable theme detection.",
            "is_discovery_related": False,
            "labeling_confidence": 0.0,
            "review_required": True,
            "labeling_model": "none (micro-cluster auto-label)",
            "labeling_prompt_version": "n/a",
        }

    def _fallback_label(self) -> dict:
        return {
            "label": "Unlabeled Cluster",
            "theme": "Theme labeling failed — manual review required.",
            "is_discovery_related": False,
            "labeling_confidence": 0.0,
            "review_required": True,
            "labeling_model": self._model,
            "labeling_prompt_version": LABELING_PROMPT_VERSION,
        }

    @staticmethod
    def _parse_json(raw: str) -> dict | list:
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
        return json.loads(text)
