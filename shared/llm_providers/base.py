from __future__ import annotations
import json
import re
from abc import ABC, abstractmethod


class ProviderError(Exception):
    """Non-retryable provider error."""


class RateLimitError(ProviderError):
    """Provider returned 429 / rate limit — router should failover."""


class LLMProvider(ABC):
    name: str = "base"

    @abstractmethod
    def complete(self, prompt: str, system: str = "", max_tokens: int = 2048) -> str:
        """Return raw text completion."""

    def complete_json(self, prompt: str, system: str = "", max_tokens: int = 2048) -> dict:
        """Return parsed JSON dict. Raises ValueError on parse failure."""
        text = self.complete(prompt, system, max_tokens)
        return _parse_json(text)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r})"


def _parse_json(text: str) -> dict:
    text = text.strip()
    # Strip markdown fences
    fence = re.search(r"```(?:json)?\s*([\s\S]+?)```", text)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try extracting the first {...} block
        match = re.search(r"\{[\s\S]+\}", text)
        if match:
            return json.loads(match.group())
        raise ValueError(f"No valid JSON found in response: {text[:200]!r}")
