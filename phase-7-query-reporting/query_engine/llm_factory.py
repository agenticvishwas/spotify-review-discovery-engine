"""Builds the LLM provider used for NL-query answer synthesis.

Mirrors Phase 5's provider-rotation pattern (insight_pipeline.py /
InsightLLMClient): try Anthropic first, fall back to Groq, then a local
Ollama model. Reuses shared/llm_providers so a rate limit on one provider
automatically rotates to the next instead of failing the query.
"""
from __future__ import annotations
import sys
from pathlib import Path
from typing import Any, Optional

_SHARED_ROOT = Path(__file__).resolve().parent.parent.parent / "shared"


def _ensure_shared_on_path() -> None:
    root = str(_SHARED_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)


def configured_provider_names(config: Any) -> list[str]:
    """Names of providers config has credentials/settings for, in priority order."""
    names = []
    if config.anthropic_api_key:
        names.append("anthropic")
    if config.groq_api_key:
        names.append("groq")
    if config.ollama_enabled:
        names.append("ollama")
    return names


def build_llm_provider(config: Any) -> Optional[Any]:
    """Returns a single provider, a failover router across several, or None."""
    _ensure_shared_on_path()
    from llm_providers.anthropic_provider import AnthropicProvider
    from llm_providers.openai_compat_provider import groq_provider, ollama_provider
    from llm_providers.router import LLMRouter

    providers = []
    if config.anthropic_api_key:
        providers.append(AnthropicProvider(api_key=config.anthropic_api_key, model=config.llm_model))
    if config.groq_api_key:
        providers.append(groq_provider(api_key=config.groq_api_key, model=config.groq_model))
    if config.ollama_enabled:
        providers.append(ollama_provider(model=config.ollama_model, base_url=config.ollama_base_url))

    if not providers:
        return None
    if len(providers) == 1:
        return providers[0]
    return LLMRouter(providers=providers, strategy=config.llm_strategy)
