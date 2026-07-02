from __future__ import annotations
import logging
from .base import LLMProvider, ProviderError, RateLimitError

logger = logging.getLogger(__name__)


class AnthropicProvider(LLMProvider):
    """
    Anthropic Claude via the official SDK.

    Recommended models (fastest → most capable):
      claude-haiku-4-5-20251001   — fastest, cheapest, good for bulk extraction
      claude-sonnet-4-6           — balanced (default)
      claude-opus-4-8             — highest quality, use for insight generation
    """

    name = "anthropic"

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6"):
        import anthropic  # type: ignore[import]
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def complete(self, prompt: str, system: str = "", max_tokens: int = 2048) -> str:
        try:
            kwargs: dict = {
                "model": self._model,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            }
            if system:
                kwargs["system"] = system
            resp = self._client.messages.create(**kwargs)
            text = resp.content[0].text
            logger.debug("anthropic model=%s tokens_in=%d tokens_out=%d",
                         self._model, resp.usage.input_tokens, resp.usage.output_tokens)
            return text
        except Exception as exc:
            msg = str(exc)
            if "rate_limit" in msg.lower() or "429" in msg or "overloaded" in msg.lower():
                raise RateLimitError(f"Anthropic rate limit: {exc}") from exc
            raise ProviderError(f"Anthropic error: {exc}") from exc
