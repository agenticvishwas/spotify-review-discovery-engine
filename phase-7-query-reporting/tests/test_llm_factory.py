"""Tests for llm_factory — provider selection, defaults, and rotation wiring."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import Phase7Config
from query_engine.llm_factory import build_llm_provider, configured_provider_names


def _config(**overrides) -> Phase7Config:
    base = dict(anthropic_api_key=None, groq_api_key=None, ollama_enabled=False)
    base.update(overrides)
    return Phase7Config(**base)


def test_no_providers_configured_returns_none():
    config = _config()
    assert build_llm_provider(config) is None
    assert configured_provider_names(config) == []


def test_single_anthropic_provider_returned_directly():
    config = _config(anthropic_api_key="sk-ant-test")
    llm = build_llm_provider(config)
    assert llm.name == "anthropic"
    assert configured_provider_names(config) == ["anthropic"]


def test_single_groq_provider_returned_directly():
    config = _config(groq_api_key="gsk-test")
    llm = build_llm_provider(config)
    assert llm.name.startswith("groq:")
    assert configured_provider_names(config) == ["groq"]


def test_single_ollama_provider_returned_directly():
    config = _config(ollama_enabled=True, ollama_model="qwen2.5:7b",
                      ollama_base_url="http://localhost:11434/v1")
    llm = build_llm_provider(config)
    assert llm.name.startswith("ollama:")
    assert configured_provider_names(config) == ["ollama"]


def test_multiple_providers_wrapped_in_failover_router():
    config = _config(anthropic_api_key="sk-ant-test", groq_api_key="gsk-test",
                      ollama_enabled=True)
    llm = build_llm_provider(config)
    names = [h["name"] for h in llm.provider_health()]
    assert names[0] == "anthropic"
    assert names[1].startswith("groq:")
    assert names[2].startswith("ollama:")
    assert configured_provider_names(config) == ["anthropic", "groq", "ollama"]


def test_llm_strategy_passed_through_to_router():
    config = _config(anthropic_api_key="sk-ant-test", groq_api_key="gsk-test",
                      llm_strategy="round_robin")
    llm = build_llm_provider(config)
    assert llm._strategy == "round_robin"


def test_ollama_disabled_by_default_from_env(monkeypatch):
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    config = Phase7Config.from_env()
    assert config.ollama_enabled is False
    assert build_llm_provider(config) is None


def test_ollama_enabled_via_env_model_only(monkeypatch):
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.2:3b")
    config = Phase7Config.from_env()
    assert config.ollama_enabled is True
    assert config.ollama_model == "llama3.2:3b"
    assert config.ollama_base_url == "http://localhost:11434/v1"
