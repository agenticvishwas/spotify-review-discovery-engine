"""Unit tests for ThemeLabeler (mocked LLM)."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from themes.theme_labeler import ThemeLabeler, LOW_CONFIDENCE_THRESHOLD


def _make_mock_response(label: str, theme: str, is_discovery: bool, confidence: float) -> MagicMock:
    payload = json.dumps({
        "label": label,
        "theme": theme,
        "is_discovery_related": is_discovery,
        "confidence": confidence,
    })
    msg = MagicMock()
    msg.content = [MagicMock(text=payload)]
    return msg


class TestThemeLabelerParsing:
    @pytest.fixture
    def labeler(self):
        # Bypass __init__ so tests run without anthropic/openai installed
        inst = ThemeLabeler.__new__(ThemeLabeler)
        inst._provider = "anthropic"
        inst._model = "claude-sonnet-4-6"
        inst._single_prompt_template = (
            Path(__file__).parent.parent / "themes" / "prompts" / "cluster_labeling_v1.0.md"
        ).read_text(encoding="utf-8")
        inst._client = MagicMock()
        return inst

    def test_valid_response_parsed(self, labeler):
        labeler._client.messages.create.return_value = _make_mock_response(
            "Repeat Algorithm Issues", "Users frustrated by repetitive recommendations", True, 0.85
        )
        result = labeler._label_single(["Review about repetitive songs"])
        assert result["label"] == "Repeat Algorithm Issues"
        assert result["is_discovery_related"] is True
        assert result["labeling_confidence"] == 0.85
        assert result["review_required"] is False

    def test_low_confidence_sets_review_required(self, labeler):
        labeler._client.messages.create.return_value = _make_mock_response(
            "Mixed Feedback", "Various topics mentioned", False, 0.4
        )
        result = labeler._label_single(["A review"])
        assert result["review_required"] is True
        assert result["labeling_confidence"] < LOW_CONFIDENCE_THRESHOLD

    def test_generic_label_sets_review_required(self, labeler):
        labeler._client.messages.create.return_value = _make_mock_response(
            "mixed feedback", "No clear theme", False, 0.8
        )
        result = labeler._label_single(["A review"])
        assert result["review_required"] is True

    def test_api_failure_returns_safe_defaults(self, labeler):
        labeler._client.messages.create.side_effect = Exception("API timeout")
        result = labeler._label_single(["A review"])
        assert result["label"] == "Unlabeled Cluster"
        assert result["review_required"] is True
        assert result["labeling_confidence"] == 0.0

    def test_markdown_fences_stripped(self, labeler):
        payload = '```json\n{"label":"Test","theme":"A theme","is_discovery_related":false,"confidence":0.9}\n```'
        msg = MagicMock()
        msg.content = [MagicMock(text=payload)]
        labeler._client.messages.create.return_value = msg
        result = labeler._label_single(["text"])
        assert result["label"] == "Test"

    def test_label_all_updates_all_clusters(self, labeler):
        # Batch call will fall back to per-cluster (mock returns single-cluster JSON);
        # per-cluster path calls _label_single which handles the mock correctly.
        labeler._client.messages.create.return_value = _make_mock_response(
            "Some Label", "Some theme", False, 0.75
        )
        clusters = [
            {"id": "c1", "is_micro_cluster": False, "representative_review_ids": ["r1", "r2"]},
            {"id": "c2", "is_micro_cluster": False, "representative_review_ids": ["r3"]},
        ]
        text_lookup = {"r1": "text1", "r2": "text2", "r3": "text3"}
        result = labeler.label_all(clusters, text_lookup)
        assert len(result) == 2
        for c in result:
            assert c["label"] == "Some Label"

    def test_parse_json_plain(self):
        raw = '{"label":"X","theme":"Y","is_discovery_related":true,"confidence":0.9}'
        parsed = ThemeLabeler._parse_json(raw)
        assert parsed["label"] == "X"

    def test_parse_json_fenced(self):
        raw = "```json\n{\"label\":\"X\",\"theme\":\"Y\",\"is_discovery_related\":true,\"confidence\":0.9}\n```"
        parsed = ThemeLabeler._parse_json(raw)
        assert parsed["label"] == "X"
