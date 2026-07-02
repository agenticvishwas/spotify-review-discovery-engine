"""Multi-provider LLM client for structured review extraction.

Supports Anthropic (Claude), Groq (Llama/Mixtral), and Ollama (local models).
All providers return the same (extracted_dict, total_tokens) tuple via extract().

Provider     Key source              Default model
-----------  ----------------------  --------------------------
anthropic    ANTHROPIC_API_KEY       claude-sonnet-4-6
groq         GROQ_API_KEY            llama-3.3-70b-versatile
ollama       no key required         llama3.1 (local)
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

_TOOL_SCHEMA_PATH = Path(__file__).parent.parent / "schemas" / "extraction_tool.json"
_PROMPT_DIR = Path(__file__).parent.parent / "prompts"

CURRENT_PROMPT_VERSION = "1.3"

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

# Max retry attempts and backoff config (applies to all providers)
_MAX_RETRIES = 5
_BACKOFF_BASE = 2
_BACKOFF_MIN = 4
_BACKOFF_MAX = 60


def _load_tool_schema() -> dict:
    return json.loads(_TOOL_SCHEMA_PATH.read_text(encoding="utf-8"))


def _load_prompt(version: str, provider: str = "anthropic") -> dict:
    """Load prompt config, preferring a provider-specific file if one exists.

    Resolution order:
      1. review_analysis_v{version}_{provider}.json  (e.g. v1.3_ollama.json)
      2. review_analysis_v{version}.json             (generic fallback)
    """
    specific = _PROMPT_DIR / f"review_analysis_v{version}_{provider}.json"
    if specific.exists():
        logger.debug("prompt=loaded path=%s", specific.name)
        return json.loads(specific.read_text(encoding="utf-8"))
    generic = _PROMPT_DIR / f"review_analysis_v{version}.json"
    logger.debug("prompt=loaded path=%s (no provider-specific file found)", generic.name)
    return json.loads(generic.read_text(encoding="utf-8"))


def _build_json_system_prompt(
    base_system: str, tool_schema: dict, schema_hint: Optional[str] = None
) -> str:
    """Build a system prompt for JSON mode by embedding the output schema inline.

    If schema_hint is provided (from the prompt JSON file), it is used directly —
    this is the fast path for provider-specific prompts with pre-written compact hints.

    Otherwise the schema is built dynamically from the tool definition — accurate
    but verbose (~300 tokens vs ~110 for a hand-written hint).
    """
    if schema_hint:
        return f"{base_system}\n\n{schema_hint}"

    props = tool_schema.get("input_schema", {}).get("properties", {})
    required = tool_schema.get("input_schema", {}).get("required", [])

    field_lines = []
    for name, spec in props.items():
        req_marker = " (required)" if name in required else " (optional, omit if unknown)"
        type_info = spec.get("type", "string")
        if "enum" in spec:
            type_info = f"one of: {spec['enum']}"
        elif type_info == "array" and "items" in spec:
            items = spec["items"]
            if "enum" in items:
                type_info = f"array of values from: {items['enum']}"
            else:
                type_info = "array of strings"
        elif isinstance(type_info, list):
            type_info = " or ".join(str(t) for t in type_info)
        desc = spec.get("description", "")
        field_lines.append(f'  "{name}": {type_info}{req_marker} — {desc}')

    schema_block = "\n".join(field_lines)
    return (
        f"{base_system}\n\n"
        "You must respond with a single valid JSON object containing these fields:\n"
        f"{schema_block}\n\n"
        "Return only the JSON object. No markdown, no explanation, no code fences."
    )


def _to_openai_tool(anthropic_tool: dict) -> dict:
    """Convert Anthropic tool schema to OpenAI function-calling format."""
    return {
        "type": "function",
        "function": {
            "name": anthropic_tool["name"],
            "description": anthropic_tool["description"],
            "parameters": anthropic_tool["input_schema"],
        },
    }


class LLMExtractionError(Exception):
    """Raised when the provider response cannot be parsed into structured fields."""


class LLMClient:
    """Unified async LLM client that dispatches to Anthropic, Groq, or Ollama.

    Usage:
        client = LLMClient(provider="anthropic")          # uses ANTHROPIC_API_KEY
        client = LLMClient(provider="groq")               # uses GROQ_API_KEY
        client = LLMClient(provider="ollama")             # no key needed
        client = LLMClient(provider="ollama", model="mistral")
    """

    def __init__(
        self,
        provider: str = "anthropic",
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        prompt_version: str = CURRENT_PROMPT_VERSION,
    ):
        if provider not in PROVIDER_DEFAULTS:
            raise ValueError(
                f"Unknown provider '{provider}'. "
                f"Choose from: {list(PROVIDER_DEFAULTS)}"
            )

        cfg = PROVIDER_DEFAULTS[provider]
        self._provider = provider
        self._prompt_cfg = _load_prompt(prompt_version, provider)
        self._tool = _load_tool_schema()
        self._temperature = self._prompt_cfg["temperature"]
        self._max_tokens = self._prompt_cfg["max_tokens"]
        self._system = self._prompt_cfg["system"]

        # Model: explicit override > provider default (prompt config model only for anthropic)
        if model:
            self._model = model
        elif provider == "anthropic":
            self._model = self._prompt_cfg["model"]
        else:
            self._model = cfg["model"]

        # Resolve API key
        resolved_key = api_key or (os.environ.get(cfg["env_key"]) if cfg["env_key"] else None)
        if cfg["requires_key"] and not resolved_key:
            env_var = cfg["env_key"]
            raise EnvironmentError(
                f"Provider '{provider}' requires an API key. "
                f"Set the {env_var} environment variable or pass api_key= to LLMClient."
            )

        # Build the async client
        if provider == "anthropic":
            import anthropic
            self._async_client = anthropic.AsyncAnthropic(api_key=resolved_key)
            self._retryable_errors = self._anthropic_retryable_errors()
        else:
            import openai
            self._async_client = openai.AsyncOpenAI(
                api_key=resolved_key or "ollama",
                base_url=cfg["base_url"],
            )
            self._retryable_errors = self._openai_retryable_errors()

        # Ollama uses native JSON mode instead of tool_use — faster and more reliable
        # with small models. Groq uses tool_use (well-supported there).
        self._use_json_mode = (provider == "ollama")
        if self._use_json_mode:
            schema_hint = self._prompt_cfg.get("json_schema_hint")
            self._json_system = _build_json_system_prompt(self._system, self._tool, schema_hint)
            if schema_hint:
                logger.debug("prompt=using pre-written schema_hint version=%s", prompt_version)
            else:
                logger.debug("prompt=using dynamic schema builder version=%s", prompt_version)
        else:
            self._json_system = None

    # ── Public interface ─────────────────────────────────────────────────────

    @property
    def model(self) -> str:
        return self._model

    @property
    def prompt_version(self) -> str:
        return self._prompt_cfg["version"]

    async def extract(
        self,
        clean_text: str,
        platform: str,
        normalized_rating: Optional[float],
    ) -> tuple[dict[str, Any], int]:
        """Return (extracted_fields, total_tokens). Retries on transient errors."""
        rating_str = f"{normalized_rating}/5" if normalized_rating is not None else "not provided"
        user_message = self._prompt_cfg["user_template"].format(
            platform=platform,
            normalized_rating=rating_str,
            clean_text=clean_text,
        )
        return await self._call_with_retry(user_message)

    # ── Provider dispatch ────────────────────────────────────────────────────

    async def _call_with_retry(self, user_message: str) -> tuple[dict[str, Any], int]:
        last_err: Optional[Exception] = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                if self._provider == "anthropic":
                    return await self._call_anthropic(user_message)
                elif self._use_json_mode:
                    return await self._call_ollama_json(user_message)
                else:
                    return await self._call_openai_compat(user_message)
            except self._retryable_errors as exc:
                wait = min(_BACKOFF_MIN * (_BACKOFF_BASE ** (attempt - 1)), _BACKOFF_MAX)
                logger.warning(
                    "provider=%s attempt=%d/%d retryable_error=%s waiting=%.0fs",
                    self._provider, attempt, _MAX_RETRIES, exc, wait,
                )
                await asyncio.sleep(wait)
                last_err = exc
            except LLMExtractionError:
                raise
            except Exception as exc:
                raise LLMExtractionError(f"Unexpected error from {self._provider}: {exc}") from exc

        raise LLMExtractionError(
            f"All {_MAX_RETRIES} attempts failed for provider={self._provider}: {last_err}"
        )

    async def _call_anthropic(self, user_message: str) -> tuple[dict[str, Any], int]:
        response = await self._async_client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
            system=self._system,
            messages=[{"role": "user", "content": user_message}],
            tools=[self._tool],
            tool_choice={"type": "any"},
        )
        total_tokens = response.usage.input_tokens + response.usage.output_tokens
        for block in response.content:
            if block.type == "tool_use" and block.name == "extract_review_signals":
                return block.input, total_tokens
        raise LLMExtractionError(
            f"No tool_use block in Anthropic response. "
            f"stop_reason={response.stop_reason}, "
            f"content_types={[b.type for b in response.content]}"
        )

    async def _call_ollama_json(self, user_message: str) -> tuple[dict[str, Any], int]:
        """Ollama-specific path using native JSON mode — no tool_use overhead.

        Embeds the output schema in the system prompt and requests
        response_format=json_object, which Ollama enforces at the grammar level.
        This is ~2x faster than tool_use for small models and avoids tool_call
        parse failures that trigger retries.
        """
        response = await self._async_client.chat.completions.create(
            model=self._model,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
            messages=[
                {"role": "system", "content": self._json_system},
                {"role": "user", "content": user_message},
            ],
            response_format={"type": "json_object"},
        )
        usage = response.usage
        total_tokens = (usage.prompt_tokens + usage.completion_tokens) if usage else 0

        raw_content = response.choices[0].message.content or ""
        try:
            return json.loads(raw_content), total_tokens
        except json.JSONDecodeError as exc:
            raise LLMExtractionError(
                f"Ollama JSON mode returned non-JSON content: {exc}. "
                f"Content preview: {raw_content[:200]}"
            ) from exc

    async def _call_openai_compat(self, user_message: str) -> tuple[dict[str, Any], int]:
        openai_tool = _to_openai_tool(self._tool)
        response = await self._async_client.chat.completions.create(
            model=self._model,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
            messages=[
                {"role": "system", "content": self._system},
                {"role": "user", "content": user_message},
            ],
            tools=[openai_tool],
            tool_choice={"type": "function", "function": {"name": "extract_review_signals"}},
        )
        usage = response.usage
        total_tokens = (usage.prompt_tokens + usage.completion_tokens) if usage else 0

        choice = response.choices[0]
        tool_calls = getattr(choice.message, "tool_calls", None)
        if not tool_calls:
            raise LLMExtractionError(
                f"No tool_calls in {self._provider} response. "
                f"finish_reason={choice.finish_reason}"
            )
        try:
            return json.loads(tool_calls[0].function.arguments), total_tokens
        except json.JSONDecodeError as exc:
            raise LLMExtractionError(
                f"tool_calls[0].function.arguments is not valid JSON: {exc}"
            ) from exc

    # ── Error type helpers ───────────────────────────────────────────────────

    @staticmethod
    def _anthropic_retryable_errors() -> tuple:
        import anthropic
        return (
            anthropic.RateLimitError,
            anthropic.APITimeoutError,
            anthropic.APIConnectionError,
        )

    @staticmethod
    def _openai_retryable_errors() -> tuple:
        import openai
        return (
            openai.RateLimitError,
            openai.APITimeoutError,
            openai.APIConnectionError,
        )
