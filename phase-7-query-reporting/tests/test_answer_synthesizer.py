"""Tests for AnswerSynthesizer — uses a stub LLM provider."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from query_engine.answer_synthesizer import AnswerSynthesizer


class _StubLLM:
    def __init__(self, response: dict):
        self._resp = response

    def complete(self, prompt: str, system: str = "", max_tokens: int = 1024) -> str:
        return json.dumps(self._resp)


_VALID_RESPONSE = {
    "answer": "Users struggle because the algorithm is repetitive.",
    "confidence": "high",
    "key_findings": [
        {
            "finding": "Algorithm repetition is the top complaint",
            "evidence_count": 312,
            "verbatims": ["Same songs every day", "No variety"],
        }
    ],
    "caveats": None,
}

_QUERY_RESULTS = {
    "intent": "discovery_friction",
    "steps": [
        {
            "table": "insights",
            "kind": "sql",
            "description": "test",
            "count": 1,
            "rows": [
                {
                    "id": "abc123",
                    "title": "Algorithm Repetition",
                    "description": "Users hear same songs repeatedly",
                    "confidence_score": 0.85,
                    "insight_type": "problem",
                    "opportunity_score": 0.78,
                }
            ],
        }
    ],
}


def test_synthesize_returns_expected_shape():
    synth = AnswerSynthesizer(_StubLLM(_VALID_RESPONSE))
    result = synth.synthesize("Why is discovery repetitive?", _QUERY_RESULTS, [])
    assert "answer" in result
    assert "confidence" in result
    assert "key_findings" in result
    assert "question" in result
    assert "generated_at" in result
    assert "related_insights" in result


def test_synthesize_populates_related_insights():
    synth = AnswerSynthesizer(_StubLLM(_VALID_RESPONSE))
    result = synth.synthesize("test", _QUERY_RESULTS, [])
    assert "abc123" in result["related_insights"]


def test_synthesize_handles_llm_error():
    class _FailLLM:
        def complete(self, *args, **kwargs):
            raise RuntimeError("network error")

    synth = AnswerSynthesizer(_FailLLM())
    result = synth.synthesize("test", _QUERY_RESULTS, [])
    assert result["confidence"] == "low"
    assert "caveats" in result


def test_synthesize_strips_markdown_fences():
    class _FencedLLM:
        def complete(self, *args, **kwargs):
            return f"```json\n{json.dumps(_VALID_RESPONSE)}\n```"

    synth = AnswerSynthesizer(_FencedLLM())
    result = synth.synthesize("test", _QUERY_RESULTS, [])
    assert result["answer"] == _VALID_RESPONSE["answer"]


def test_format_verbatims_filters_empty():
    synth = AnswerSynthesizer(_StubLLM(_VALID_RESPONSE))
    verbatims = [
        {"verbatim": "Great app", "platform": "app_store", "normalized_rating": 5.0},
        {"verbatim": "", "platform": "reddit"},
        {"platform": "google_play"},  # no verbatim key
    ]
    formatted = synth._format_verbatims(verbatims)
    assert len(formatted) == 1
    assert formatted[0]["text"] == "Great app"
