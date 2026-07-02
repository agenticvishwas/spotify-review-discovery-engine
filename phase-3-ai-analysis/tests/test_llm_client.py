"""Tests for LLMClient provider routing — no real API calls."""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from analyzers.llm_client import LLMClient, LLMExtractionError, _to_openai_tool, PROVIDER_DEFAULTS


SAMPLE_EXTRACTION = {
    "sentiment": "negative",
    "sentiment_score": -0.7,
    "discovery_friction_detected": True,
    "feature_mentions": ["Discover Weekly"],
    "emotion_tags": ["frustration"],
    "user_segment_signal": "power_user",
    "listening_behavior_signal": "exploratory",
    "confidence_score": 0.82,
}


class TestProviderDefaults:
    def test_all_providers_have_required_keys(self):
        for provider, cfg in PROVIDER_DEFAULTS.items():
            assert "model" in cfg, f"{provider} missing model"
            assert "requires_key" in cfg, f"{provider} missing requires_key"

    def test_ollama_does_not_require_key(self):
        assert PROVIDER_DEFAULTS["ollama"]["requires_key"] is False

    def test_anthropic_and_groq_require_key(self):
        assert PROVIDER_DEFAULTS["anthropic"]["requires_key"] is True
        assert PROVIDER_DEFAULTS["groq"]["requires_key"] is True


class TestToolSchemaConversion:
    def test_to_openai_tool_structure(self):
        anthropic_tool = {
            "name": "extract_review_signals",
            "description": "Extract signals",
            "input_schema": {"type": "object", "properties": {}},
        }
        result = _to_openai_tool(anthropic_tool)
        assert result["type"] == "function"
        assert result["function"]["name"] == "extract_review_signals"
        assert result["function"]["parameters"] == anthropic_tool["input_schema"]

    def test_to_openai_tool_preserves_description(self):
        tool = {
            "name": "test_tool",
            "description": "A test tool",
            "input_schema": {"type": "object"},
        }
        result = _to_openai_tool(tool)
        assert result["function"]["description"] == "A test tool"


class TestLLMClientInit:
    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            LLMClient(provider="openai_gpt")

    def test_anthropic_missing_key_raises(self):
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(EnvironmentError, match="ANTHROPIC_API_KEY"):
                LLMClient(provider="anthropic")

    def test_groq_missing_key_raises(self):
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(EnvironmentError, match="GROQ_API_KEY"):
                LLMClient(provider="groq")

    def test_ollama_no_key_needed(self):
        # Should not raise even with no env vars
        with patch.dict("os.environ", {}, clear=True):
            with patch("openai.AsyncOpenAI"):
                client = LLMClient(provider="ollama")
                assert client._provider == "ollama"

    def test_model_override_respected(self):
        with patch.dict("os.environ", {}, clear=True):
            with patch("openai.AsyncOpenAI"):
                client = LLMClient(provider="ollama", model="mistral")
                assert client._model == "mistral"

    def test_anthropic_uses_prompt_model_by_default(self):
        with patch("anthropic.AsyncAnthropic"):
            client = LLMClient(provider="anthropic", api_key="fake-key")
            assert client._model == "claude-sonnet-4-6"

    def test_groq_uses_provider_default_model(self):
        with patch("openai.AsyncOpenAI"):
            client = LLMClient(provider="groq", api_key="fake-key")
            assert client._model == PROVIDER_DEFAULTS["groq"]["model"]


class TestAnthropicExtract:
    def _make_anthropic_response(self, data: dict):
        block = MagicMock()
        block.type = "tool_use"
        block.name = "extract_review_signals"
        block.input = data

        usage = MagicMock()
        usage.input_tokens = 200
        usage.output_tokens = 100

        response = MagicMock()
        response.content = [block]
        response.usage = usage
        response.stop_reason = "tool_use"
        return response

    def test_extract_returns_dict_and_tokens(self):
        import asyncio
        mock_response = self._make_anthropic_response(SAMPLE_EXTRACTION)

        with patch("anthropic.AsyncAnthropic") as MockClient:
            instance = MockClient.return_value
            instance.messages.create = AsyncMock(return_value=mock_response)

            client = LLMClient(provider="anthropic", api_key="fake-key")
            result, tokens = asyncio.run(
                client.extract("Great app", "app_store", 4.0)
            )

        assert result["sentiment"] == "negative"
        assert tokens == 300

    def test_no_tool_use_block_raises(self):
        import asyncio
        block = MagicMock()
        block.type = "text"

        usage = MagicMock()
        usage.input_tokens = 100
        usage.output_tokens = 50

        response = MagicMock()
        response.content = [block]
        response.usage = usage
        response.stop_reason = "end_turn"

        with patch("anthropic.AsyncAnthropic") as MockClient:
            instance = MockClient.return_value
            instance.messages.create = AsyncMock(return_value=response)

            client = LLMClient(provider="anthropic", api_key="fake-key")
            with pytest.raises(LLMExtractionError, match="No tool_use block"):
                asyncio.run(client.extract("Some review", "google_play", None))


class TestOpenAICompatExtract:
    def _make_openai_response(self, data: dict):
        func_call = MagicMock()
        func_call.arguments = json.dumps(data)

        tool_call = MagicMock()
        tool_call.function = func_call

        message = MagicMock()
        message.tool_calls = [tool_call]

        choice = MagicMock()
        choice.message = message
        choice.finish_reason = "tool_calls"

        usage = MagicMock()
        usage.prompt_tokens = 180
        usage.completion_tokens = 120

        response = MagicMock()
        response.choices = [choice]
        response.usage = usage
        return response

    def test_groq_extract_returns_dict_and_tokens(self):
        import asyncio
        mock_response = self._make_openai_response(SAMPLE_EXTRACTION)

        with patch("openai.AsyncOpenAI") as MockClient:
            instance = MockClient.return_value
            instance.chat.completions.create = AsyncMock(return_value=mock_response)

            client = LLMClient(provider="groq", api_key="fake-groq-key")
            result, tokens = asyncio.run(
                client.extract("Discover Weekly is broken", "app_store", 2.0)
            )

        assert result["sentiment"] == "negative"
        assert tokens == 300

    def _make_ollama_response(self, data: dict):
        """Ollama JSON mode returns content as a plain JSON string, not tool_calls."""
        message = MagicMock()
        message.content = json.dumps(data)

        choice = MagicMock()
        choice.message = message
        choice.finish_reason = "stop"

        usage = MagicMock()
        usage.prompt_tokens = 180
        usage.completion_tokens = 120

        response = MagicMock()
        response.choices = [choice]
        response.usage = usage
        return response

    def test_ollama_extract_uses_json_mode(self):
        import asyncio
        mock_response = self._make_ollama_response(SAMPLE_EXTRACTION)

        with patch("openai.AsyncOpenAI") as MockClient:
            instance = MockClient.return_value
            instance.chat.completions.create = AsyncMock(return_value=mock_response)

            client = LLMClient(provider="ollama")
            result, tokens = asyncio.run(
                client.extract("Great discovery features", "reddit", None)
            )

        assert result["discovery_friction_detected"] is True
        assert tokens == 300

    def test_ollama_invalid_json_content_raises(self):
        import asyncio
        message = MagicMock()
        message.content = "Sorry, I cannot do that."  # model ignored JSON mode

        choice = MagicMock()
        choice.message = message
        choice.finish_reason = "stop"

        response = MagicMock()
        response.choices = [choice]
        response.usage = None

        with patch("openai.AsyncOpenAI") as MockClient:
            instance = MockClient.return_value
            instance.chat.completions.create = AsyncMock(return_value=response)

            client = LLMClient(provider="ollama")
            with pytest.raises(LLMExtractionError, match="non-JSON"):
                asyncio.run(client.extract("Some text", "app_store", 3.0))

    def test_groq_no_tool_calls_raises(self):
        import asyncio
        message = MagicMock()
        message.tool_calls = None

        choice = MagicMock()
        choice.message = message
        choice.finish_reason = "stop"

        response = MagicMock()
        response.choices = [choice]
        response.usage = None

        with patch("openai.AsyncOpenAI") as MockClient:
            instance = MockClient.return_value
            instance.chat.completions.create = AsyncMock(return_value=response)

            client = LLMClient(provider="groq", api_key="fake-key")
            with pytest.raises(LLMExtractionError, match="No tool_calls"):
                asyncio.run(client.extract("Some text", "app_store", 3.0))

    def test_invalid_json_in_arguments_raises(self):
        import asyncio
        func_call = MagicMock()
        func_call.arguments = "not valid json {"

        tool_call = MagicMock()
        tool_call.function = func_call

        message = MagicMock()
        message.tool_calls = [tool_call]

        choice = MagicMock()
        choice.message = message
        choice.finish_reason = "tool_calls"

        response = MagicMock()
        response.choices = [choice]
        response.usage = None

        with patch("openai.AsyncOpenAI") as MockClient:
            instance = MockClient.return_value
            instance.chat.completions.create = AsyncMock(return_value=response)

            client = LLMClient(provider="groq", api_key="fake-key")
            with pytest.raises(LLMExtractionError, match="not valid JSON"):
                asyncio.run(client.extract("Some text", "app_store", 3.0))
