from __future__ import annotations
import logging
from .base import LLMProvider, ProviderError, RateLimitError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pre-configured provider specs
# ---------------------------------------------------------------------------

GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# Groq models — pick by speed vs quality:
#   llama-3.1-8b-instant    — fastest (good for bulk Phase 3)
#   llama-3.3-70b-versatile — balanced
#   mixtral-8x7b-32768      — good context window
GROQ_DEFAULT_MODEL = "llama-3.3-70b-versatile"

OLLAMA_BASE_URL = "http://localhost:11434/v1"
# Ollama/Qwen models — local, zero cost:
#   qwen2.5:7b    — fast, good quality for structured extraction
#   qwen2.5:14b   — higher quality
#   llama3.2:3b   — very fast for low-priority tasks
OLLAMA_DEFAULT_MODEL = "qwen2.5:7b"

# Alibaba Qwen API (OpenAI-compatible)
QWEN_API_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
QWEN_DEFAULT_MODEL = "qwen-plus"


class OpenAICompatProvider(LLMProvider):
    """
    Generic OpenAI-compatible provider.
    Supports Groq, Ollama, Qwen API, and standard OpenAI.

    Forces JSON output via response_format when the provider supports it
    (Groq and Ollama do; some others may not).
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        name: str,
        force_json: bool = True,
    ):
        from openai import OpenAI  # type: ignore[import]
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        self.name = name
        self._force_json = force_json

    def complete(self, prompt: str, system: str = "", max_tokens: int = 2048) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        kwargs: dict = {
            "model": self._model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if self._force_json:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            resp = self._client.chat.completions.create(**kwargs)
            text = resp.choices[0].message.content or ""
            logger.debug("provider=%s model=%s tokens=%s",
                         self.name, self._model,
                         getattr(resp.usage, "total_tokens", "?"))
            return text
        except Exception as exc:
            msg = str(exc)
            if "rate_limit" in msg.lower() or "429" in msg or "too many" in msg.lower():
                raise RateLimitError(f"{self.name} rate limit: {exc}") from exc
            if "connection" in msg.lower() or "refused" in msg.lower():
                raise RateLimitError(f"{self.name} unavailable: {exc}") from exc
            raise ProviderError(f"{self.name} error: {exc}") from exc


# ---------------------------------------------------------------------------
# Factory helpers — import and call these instead of constructing directly
# ---------------------------------------------------------------------------

def groq_provider(api_key: str, model: str = GROQ_DEFAULT_MODEL) -> OpenAICompatProvider:
    return OpenAICompatProvider(
        api_key=api_key,
        base_url=GROQ_BASE_URL,
        model=model,
        name=f"groq:{model}",
    )


def ollama_provider(
    model: str = OLLAMA_DEFAULT_MODEL,
    base_url: str = OLLAMA_BASE_URL,
) -> OpenAICompatProvider:
    return OpenAICompatProvider(
        api_key="ollama",  # Ollama ignores the key
        base_url=base_url,
        model=model,
        name=f"ollama:{model}",
    )


def qwen_api_provider(api_key: str, model: str = QWEN_DEFAULT_MODEL) -> OpenAICompatProvider:
    return OpenAICompatProvider(
        api_key=api_key,
        base_url=QWEN_API_BASE_URL,
        model=model,
        name=f"qwen:{model}",
    )
