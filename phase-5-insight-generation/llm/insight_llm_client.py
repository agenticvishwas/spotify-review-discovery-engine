"""Multi-provider LLM client with automatic provider rotation for Phase 5.

Unlike Phase 3's single-provider client, this client manages an ordered pool of
providers. When a provider hits its rate limit, the client immediately rotates to
the next available provider and enforces a per-provider cooldown. This is the
primary mechanism for surviving free-tier TPM limits.

Provider pool strategy
──────────────────────
  1. Try providers in configured order (highest quality → fastest/free).
  2. On RateLimitError: mark that provider in cooldown, move to the next.
  3. On non-rate-limit transient errors: retry the same provider with
     exponential back-off (up to _MAX_RETRIES attempts).
  4. After cooldown expires the provider rejoins the rotation automatically.

Supported providers
───────────────────
  anthropic — native tool_use for structured JSON (highest quality)
  groq      — OpenAI-compatible tool_use (fast inference, low free-tier TPM)
  ollama    — local models via JSON mode (unlimited, no cost)
              Supported models: llama3.1, llama3.2, mistral, qwen2.5:7b,
                                qwen2.5:14b, qwen2.5:72b, qwen3:8b, etc.

Usage
─────
  cfgs = [
      {"provider": "anthropic", "model": "claude-sonnet-4-6"},
      {"provider": "groq",      "model": "llama-3.3-70b-versatile"},
      {"provider": "ollama",    "model": "qwen2.5:7b"},
  ]
  client = InsightLLMClient(cfgs)
  result, tokens, model = await client.call(
      system="You are ...", user_message="...", tool=tool_schema
  )
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

_MAX_RETRIES = 4          # per-provider transient-error retries
_BACKOFF_BASE = 2
_BACKOFF_MIN_SECS = 3
_BACKOFF_MAX_SECS = 45

PROVIDER_DEFAULTS: dict[str, dict] = {
    "anthropic": {
        "model": "claude-sonnet-4-6",
        "base_url": None,
        "env_key": "ANTHROPIC_API_KEY",
        "requires_key": True,
        "use_json_mode": False,
        "tpm_cooldown_secs": 65.0,   # Anthropic: ~60s TPM window
    },
    "groq": {
        "model": "llama-3.3-70b-versatile",
        "base_url": "https://api.groq.com/openai/v1",
        "env_key": "GROQ_API_KEY",
        "requires_key": True,
        "use_json_mode": False,
        "tpm_cooldown_secs": 32.0,   # Groq free: ~30s RPM/TPM reset
    },
    "ollama": {
        "model": "llama3.1",
        "base_url": "http://localhost:11434/v1",
        "env_key": None,
        "requires_key": False,
        "use_json_mode": True,
        "tpm_cooldown_secs": 3.0,    # local — shouldn't rate-limit
    },
}

# Known Qwen models accessible via Ollama (no-key, local)
OLLAMA_QWEN_MODELS = {
    "qwen2.5:7b", "qwen2.5:14b", "qwen2.5:32b", "qwen2.5:72b",
    "qwen3:8b", "qwen3:14b", "qwen3:30b",
    "qwq:32b",
}

# Known Qwen models on Groq (if available on that account)
GROQ_QWEN_MODELS = {
    "qwen-qwq-32b", "qwen/qwen3-32b",
}


@dataclass
class _ActiveProvider:
    name: str
    model: str
    use_json_mode: bool
    tpm_cooldown_secs: float
    client: Any                          # anthropic.AsyncAnthropic | openai.AsyncOpenAI
    retryable_errors: tuple              # exception types to retry on
    rate_limit_error: type               # exception type that triggers rotation


class InsightLLMError(Exception):
    """Raised when all providers are exhausted or all retries failed."""


def _is_model_not_found(exc: Exception) -> bool:
    """Return True when the provider says the model doesn't exist (HTTP 404)."""
    # openai SDK raises openai.NotFoundError (status_code=404) for missing models.
    status_code = getattr(exc, "status_code", None)
    if status_code == 404:
        return True
    # Fallback: inspect the string representation (covers edge cases).
    msg = str(exc).lower()
    return "404" in msg and ("not found" in msg or "model" in msg)


def _to_openai_tool(anthropic_tool: dict) -> dict:
    return {
        "type": "function",
        "function": {
            "name": anthropic_tool["name"],
            "description": anthropic_tool["description"],
            "parameters": anthropic_tool["input_schema"],
        },
    }


def _build_ollama_system(base_system: str, tool: Optional[dict]) -> str:
    """Embed the tool output schema into the system prompt for JSON mode."""
    if not tool:
        return base_system + "\n\nRespond with a single valid JSON object."

    props = tool.get("input_schema", {}).get("properties", {})
    required_fields = set(tool.get("input_schema", {}).get("required", []))
    lines = []
    for fname, spec in props.items():
        req = " (required)" if fname in required_fields else " (optional)"
        t = spec.get("type", "string")
        if "enum" in spec:
            t = f"one of: {spec['enum']}"
        elif t == "array" and "items" in spec and "enum" in spec["items"]:
            t = f"array of: {spec['items']['enum']}"
        elif isinstance(t, list):
            t = " | ".join(str(x) for x in t)
        desc = spec.get("description", "")
        lines.append(f'  "{fname}": {t}{req}' + (f" — {desc}" if desc else ""))

    schema_block = "\n".join(lines)
    return (
        f"{base_system}\n\n"
        "Respond with a single valid JSON object with these fields:\n"
        f"{schema_block}\n\n"
        "Return only the JSON object. No markdown, no code fences."
    )


class InsightLLMClient:
    """Provider-rotating async LLM client for Phase 5 insight generation.

    Manages an ordered pool of providers. Automatically rotates to the next
    provider when rate-limited, then resumes the preferred provider after
    the cooldown window expires.
    """

    def __init__(self, provider_cfgs: list[dict]):
        """
        Args:
            provider_cfgs: Ordered list of provider configs, highest priority first.
                Each dict must have "provider" key. Optional keys: "model", "api_key".
                Example:
                    [
                        {"provider": "anthropic"},
                        {"provider": "groq", "model": "llama-3.3-70b-versatile"},
                        {"provider": "ollama", "model": "qwen2.5:7b"},
                    ]
        """
        if not provider_cfgs:
            raise ValueError("At least one provider config is required.")

        self._providers: list[_ActiveProvider] = []
        self._cooldown_until: dict[str, float] = {}

        for cfg in provider_cfgs:
            provider_name = cfg["provider"]
            if provider_name not in PROVIDER_DEFAULTS:
                raise ValueError(
                    f"Unknown provider '{provider_name}'. "
                    f"Choose from: {list(PROVIDER_DEFAULTS)}"
                )
            defaults = PROVIDER_DEFAULTS[provider_name]
            model = cfg.get("model") or defaults["model"]
            api_key = cfg.get("api_key") or (
                os.environ.get(defaults["env_key"]) if defaults["env_key"] else None
            )
            if defaults["requires_key"] and not api_key:
                raise EnvironmentError(
                    f"Provider '{provider_name}' requires an API key. "
                    f"Set {defaults['env_key']} or pass api_key in the config dict."
                )

            use_json_mode = defaults["use_json_mode"]
            # Groq Qwen models work better in json mode too
            if provider_name == "groq" and model in GROQ_QWEN_MODELS:
                use_json_mode = True

            if provider_name == "anthropic":
                import anthropic as _anthropic
                client = _anthropic.AsyncAnthropic(api_key=api_key)
                retryable = (
                    _anthropic.APITimeoutError,
                    _anthropic.APIConnectionError,
                )
                rate_limit_cls = _anthropic.RateLimitError
            else:
                import openai as _openai
                client = _openai.AsyncOpenAI(
                    api_key=api_key or "ollama",
                    base_url=defaults["base_url"],
                )
                retryable = (
                    _openai.APITimeoutError,
                    _openai.APIConnectionError,
                )
                rate_limit_cls = _openai.RateLimitError

            self._providers.append(
                _ActiveProvider(
                    name=provider_name,
                    model=model,
                    use_json_mode=use_json_mode,
                    tpm_cooldown_secs=defaults["tpm_cooldown_secs"],
                    client=client,
                    retryable_errors=retryable,
                    rate_limit_error=rate_limit_cls,
                )
            )
            logger.info("provider=registered name=%s model=%s json_mode=%s",
                        provider_name, model, use_json_mode)

    # ── Public interface ──────────────────────────────────────────────────────

    @property
    def primary_model(self) -> str:
        return self._providers[0].model

    async def call(
        self,
        *,
        system: str,
        user_message: str,
        tool: Optional[dict] = None,
        max_tokens: int = 1024,
        temperature: float = 0.1,
    ) -> tuple[dict[str, Any], int, str]:
        """Dispatch to the best available provider.

        Returns:
            (result_dict, total_tokens, model_name_used)

        Raises:
            InsightLLMError: when all providers are in cooldown or all retries
                             fail for every provider.
        """
        errors: list[str] = []

        for provider in self._providers:
            cooldown_until = self._cooldown_until.get(provider.name, 0.0)
            if time.monotonic() < cooldown_until:
                remaining = cooldown_until - time.monotonic()
                logger.debug("provider=%s skipped cooldown_remaining=%.0fs", provider.name, remaining)
                errors.append(f"{provider.name}: in cooldown for {remaining:.0f}s")
                continue

            try:
                result, tokens = await self._call_with_retry(
                    provider, system, user_message, tool, max_tokens, temperature
                )
                return result, tokens, provider.model
            except _ProviderRateLimited as exc:
                self._cooldown_until[provider.name] = (
                    time.monotonic() + provider.tpm_cooldown_secs
                )
                logger.warning(
                    "provider=%s rate_limited rotating_to_next cooldown=%.0fs cause=%s",
                    provider.name, provider.tpm_cooldown_secs, exc,
                )
                errors.append(f"{provider.name}: rate_limited → {exc}")
            except InsightLLMError as exc:
                label = "model_not_found" if "not found" in str(exc).lower() else "failed"
                errors.append(f"{provider.name}: {label} → {exc}")

        raise InsightLLMError(
            f"All providers exhausted. Details: {'; '.join(errors)}"
        )

    # ── Provider dispatch ─────────────────────────────────────────────────────

    async def _call_with_retry(
        self,
        provider: _ActiveProvider,
        system: str,
        user_message: str,
        tool: Optional[dict],
        max_tokens: int,
        temperature: float,
    ) -> tuple[dict[str, Any], int]:
        last_err: Optional[Exception] = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                if provider.name == "anthropic":
                    return await self._call_anthropic(
                        provider, system, user_message, tool, max_tokens, temperature
                    )
                elif provider.use_json_mode:
                    ollama_system = _build_ollama_system(system, tool)
                    return await self._call_json_mode(
                        provider, ollama_system, user_message, max_tokens, temperature
                    )
                else:
                    return await self._call_openai_compat(
                        provider, system, user_message, tool, max_tokens, temperature
                    )
            except provider.rate_limit_error as exc:
                raise _ProviderRateLimited(provider.name, exc) from exc
            except provider.retryable_errors as exc:
                wait = min(_BACKOFF_MIN_SECS * (_BACKOFF_BASE ** (attempt - 1)), _BACKOFF_MAX_SECS)
                logger.warning(
                    "provider=%s model=%s attempt=%d/%d transient_error=%s waiting=%.0fs",
                    provider.name, provider.model, attempt, _MAX_RETRIES, exc, wait,
                )
                await asyncio.sleep(wait)
                last_err = exc
            except InsightLLMError:
                raise
            except Exception as exc:
                if _is_model_not_found(exc):
                    # No point retrying — model simply doesn't exist on this provider.
                    hint = (
                        f"  Run: ollama pull {provider.model}"
                        if provider.name == "ollama"
                        else ""
                    )
                    raise InsightLLMError(
                        f"Model '{provider.model}' not found on {provider.name}."
                        + (f"\n{hint}" if hint else "")
                    ) from exc
                raise InsightLLMError(
                    f"Unexpected error from {provider.name}: {exc}"
                ) from exc

        raise InsightLLMError(
            f"All {_MAX_RETRIES} retry attempts failed for {provider.name}: {last_err}"
        )

    async def _call_anthropic(
        self,
        provider: _ActiveProvider,
        system: str,
        user_message: str,
        tool: Optional[dict],
        max_tokens: int,
        temperature: float,
    ) -> tuple[dict[str, Any], int]:
        kwargs: dict[str, Any] = dict(
            model=provider.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user_message}],
        )
        if tool:
            kwargs["tools"] = [tool]
            kwargs["tool_choice"] = {"type": "any"}

        response = await provider.client.messages.create(**kwargs)
        total_tokens = response.usage.input_tokens + response.usage.output_tokens

        if tool:
            for block in response.content:
                if block.type == "tool_use" and block.name == tool["name"]:
                    return block.input, total_tokens
            raise InsightLLMError(
                f"No tool_use block in Anthropic response. "
                f"stop_reason={response.stop_reason} "
                f"content_types={[b.type for b in response.content]}"
            )
        else:
            raw = "".join(
                b.text for b in response.content if hasattr(b, "text")
            )
            try:
                return json.loads(raw), total_tokens
            except json.JSONDecodeError as exc:
                raise InsightLLMError(
                    f"Anthropic returned non-JSON text (no tool provided): {exc}. "
                    f"Preview: {raw[:200]}"
                ) from exc

    async def _call_json_mode(
        self,
        provider: _ActiveProvider,
        system_with_schema: str,
        user_message: str,
        max_tokens: int,
        temperature: float,
    ) -> tuple[dict[str, Any], int]:
        response = await provider.client.chat.completions.create(
            model=provider.model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system_with_schema},
                {"role": "user", "content": user_message},
            ],
            response_format={"type": "json_object"},
        )
        usage = response.usage
        total_tokens = (usage.prompt_tokens + usage.completion_tokens) if usage else 0
        raw = response.choices[0].message.content or ""
        try:
            return json.loads(raw), total_tokens
        except json.JSONDecodeError as exc:
            raise InsightLLMError(
                f"{provider.name} JSON mode returned non-JSON: {exc}. "
                f"Preview: {raw[:200]}"
            ) from exc

    async def _call_openai_compat(
        self,
        provider: _ActiveProvider,
        system: str,
        user_message: str,
        tool: Optional[dict],
        max_tokens: int,
        temperature: float,
    ) -> tuple[dict[str, Any], int]:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_message},
        ]
        kwargs: dict[str, Any] = dict(
            model=provider.model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=messages,
        )
        if tool:
            oai_tool = _to_openai_tool(tool)
            kwargs["tools"] = [oai_tool]
            kwargs["tool_choice"] = {
                "type": "function",
                "function": {"name": tool["name"]},
            }

        response = await provider.client.chat.completions.create(**kwargs)
        usage = response.usage
        total_tokens = (usage.prompt_tokens + usage.completion_tokens) if usage else 0
        choice = response.choices[0]

        if tool:
            tool_calls = getattr(choice.message, "tool_calls", None)
            if not tool_calls:
                raise InsightLLMError(
                    f"No tool_calls in {provider.name} response. "
                    f"finish_reason={choice.finish_reason}"
                )
            try:
                return json.loads(tool_calls[0].function.arguments), total_tokens
            except json.JSONDecodeError as exc:
                raise InsightLLMError(
                    f"tool_calls[0].function.arguments is not valid JSON: {exc}"
                ) from exc
        else:
            raw = choice.message.content or ""
            try:
                return json.loads(raw), total_tokens
            except json.JSONDecodeError as exc:
                raise InsightLLMError(
                    f"{provider.name} returned non-JSON (no tool provided): {exc}. "
                    f"Preview: {raw[:200]}"
                ) from exc


class _ProviderRateLimited(Exception):
    """Internal sentinel: rate limit hit on this provider, rotate to next."""

    def __init__(self, provider_name: str, cause: Exception):
        self.provider_name = provider_name
        super().__init__(f"{provider_name} rate limited: {cause}")
