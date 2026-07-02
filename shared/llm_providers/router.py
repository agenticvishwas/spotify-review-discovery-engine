"""
LLM Router — automatic failover and round-robin across providers.

Why this exists:
  Free-tier keys (Anthropic, Groq) have tight TPM limits. The router
  distributes load across providers and falls back automatically on rate
  limits, so pipelines keep running without manual intervention.

Usage:
    from shared.llm_providers.router import build_router

    router = build_router()          # auto-builds from env vars
    result = router.complete_json(prompt, system=SYSTEM_PROMPT)

Env vars (all optional — omit a key to disable that provider):
    ANTHROPIC_API_KEY   — Claude (primary)
    GROQ_API_KEY        — Groq / Llama (secondary)
    QWEN_API_KEY        — Alibaba Qwen API (tertiary)
    OLLAMA_BASE_URL     — Ollama base URL (default: http://localhost:11434)
                          Set to any value to enable Ollama as final fallback
    OLLAMA_MODEL        — Model for Ollama (default: qwen2.5:7b)
    GROQ_MODEL          — Model for Groq (default: llama-3.3-70b-versatile)
    ANTHROPIC_MODEL     — Model for Anthropic (default: claude-sonnet-4-6)
    LLM_STRATEGY        — failover | round_robin (default: failover)
"""
from __future__ import annotations
import logging
import os
import time
from typing import Literal

from .base import LLMProvider, ProviderError, RateLimitError

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_BACKOFF_BASE = 2.0  # seconds


class LLMRouter(LLMProvider):
    """
    Wraps multiple providers with failover logic.

    failover  — always try providers in order; failover on RateLimitError
    round_robin — distribute calls evenly; failover on any error
    """

    name = "router"

    def __init__(
        self,
        providers: list[LLMProvider],
        strategy: Literal["failover", "round_robin"] = "failover",
    ):
        if not providers:
            raise ValueError("LLMRouter requires at least one provider")
        self._providers = providers
        self._strategy = strategy
        self._rr_idx = 0
        self._consecutive_failures: list[int] = [0] * len(providers)
        logger.info(
            "LLMRouter initialized: strategy=%s providers=[%s]",
            strategy,
            ", ".join(p.name for p in providers),
        )

    def complete(self, prompt: str, system: str = "", max_tokens: int = 2048) -> str:
        if self._strategy == "round_robin":
            return self._round_robin(prompt, system, max_tokens)
        return self._failover(prompt, system, max_tokens)

    # ------------------------------------------------------------------
    # Strategies
    # ------------------------------------------------------------------

    def _failover(self, prompt: str, system: str, max_tokens: int) -> str:
        last_exc: Exception = ProviderError("No providers available")
        for i, provider in enumerate(self._providers):
            for attempt in range(_MAX_RETRIES):
                try:
                    result = provider.complete(prompt, system, max_tokens)
                    self._consecutive_failures[i] = 0
                    return result
                except RateLimitError as exc:
                    self._consecutive_failures[i] += 1
                    logger.warning(
                        "Rate limit on %s (attempt %d/%d) — trying next provider",
                        provider.name, attempt + 1, _MAX_RETRIES,
                    )
                    last_exc = exc
                    break  # Don't retry same provider on rate limit; move to next
                except ProviderError as exc:
                    self._consecutive_failures[i] += 1
                    wait = _BACKOFF_BASE ** attempt
                    logger.warning(
                        "Error on %s attempt %d/%d: %s — retrying in %.1fs",
                        provider.name, attempt + 1, _MAX_RETRIES, exc, wait,
                    )
                    last_exc = exc
                    if attempt < _MAX_RETRIES - 1:
                        time.sleep(wait)
        raise ProviderError(f"All providers exhausted. Last: {last_exc}") from last_exc

    def _round_robin(self, prompt: str, system: str, max_tokens: int) -> str:
        start = self._rr_idx
        n = len(self._providers)
        for _ in range(n):
            idx = self._rr_idx % n
            self._rr_idx += 1
            provider = self._providers[idx]
            try:
                result = provider.complete(prompt, system, max_tokens)
                self._consecutive_failures[idx] = 0
                return result
            except (RateLimitError, ProviderError) as exc:
                self._consecutive_failures[idx] += 1
                logger.warning("Round-robin: %s failed, trying next — %s", provider.name, exc)
        raise ProviderError("All providers failed in round-robin mode")

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def provider_health(self) -> list[dict]:
        return [
            {"name": p.name, "consecutive_failures": self._consecutive_failures[i]}
            for i, p in enumerate(self._providers)
        ]


# ---------------------------------------------------------------------------
# Convenience builder
# ---------------------------------------------------------------------------

def build_router(strategy: Literal["failover", "round_robin"] | None = None) -> LLMRouter:
    """
    Auto-builds a router from environment variables.
    Provider priority: Anthropic → Groq → Qwen → Ollama.
    Any provider whose key is absent is skipped.
    """
    from .anthropic_provider import AnthropicProvider
    from .openai_compat_provider import groq_provider, ollama_provider, qwen_api_provider

    providers: list[LLMProvider] = []

    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if anthropic_key:
        model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
        providers.append(AnthropicProvider(api_key=anthropic_key, model=model))

    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key:
        model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        providers.append(groq_provider(api_key=groq_key, model=model))

    qwen_key = os.getenv("QWEN_API_KEY")
    if qwen_key:
        model = os.getenv("QWEN_MODEL", "qwen-plus")
        providers.append(qwen_api_provider(api_key=qwen_key, model=model))

    # Ollama: enabled if OLLAMA_BASE_URL is set or if OLLAMA_MODEL is explicitly set
    ollama_url = os.getenv("OLLAMA_BASE_URL", "")
    ollama_model = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
    if ollama_url or os.getenv("OLLAMA_MODEL"):
        base = ollama_url or "http://localhost:11434"
        providers.append(ollama_provider(model=ollama_model, base_url=base + "/v1"))

    if not providers:
        raise RuntimeError(
            "No LLM providers configured. Set at least one of: "
            "ANTHROPIC_API_KEY, GROQ_API_KEY, QWEN_API_KEY, or OLLAMA_BASE_URL"
        )

    _strategy: Literal["failover", "round_robin"] = (
        strategy or os.getenv("LLM_STRATEGY", "failover")  # type: ignore[assignment]
    )
    return LLMRouter(providers=providers, strategy=_strategy)
