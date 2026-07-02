"""Unit tests for EmbeddingEngine and EmbeddingCache."""

import sys
from pathlib import Path
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from embeddings.embedding_engine import EmbeddingEngine, ReviewEmbeddingInput, EMBEDDING_DIM


class TestBuildText:
    def test_all_fields(self):
        text = EmbeddingEngine.build_text(
            clean_text="Great app",
            jtbd_signal="Find new music",
            primary_complaint="Algorithm repetitive",
            primary_praise="UI is clean",
            user_intent="Discover artists",
            feature_mentions=["radio", "playlists"],
        )
        assert "Great app" in text
        assert "Find new music" in text
        assert "Algorithm repetitive" in text
        assert "radio" in text

    def test_none_fields_skipped(self):
        text = EmbeddingEngine.build_text(
            clean_text="Only this",
            jtbd_signal=None,
            primary_complaint=None,
        )
        assert text == "Only this"

    def test_empty_feature_mentions(self):
        text = EmbeddingEngine.build_text(
            clean_text="Review text",
            jtbd_signal="signal",
            primary_complaint=None,
            feature_mentions=[],
        )
        assert text == "Review text signal"

    def test_all_none_returns_empty(self):
        text = EmbeddingEngine.build_text(
            clean_text=None,
            jtbd_signal=None,
            primary_complaint=None,
        )
        assert text == ""


class TestEmbeddingEngine:
    @pytest.fixture
    def engine(self):
        return EmbeddingEngine()

    def test_embed_returns_dict_with_correct_keys(self, engine):
        inputs = [
            ReviewEmbeddingInput(review_id="r1", text="Discover new music easily"),
            ReviewEmbeddingInput(review_id="r2", text="Algorithm keeps repeating songs"),
        ]
        result = engine.embed(inputs)
        assert set(result.keys()) == {"r1", "r2"}

    def test_embed_correct_dimensions(self, engine):
        # TF-IDF needs ≥2 texts; n_components = min(384, n-1, vocab)
        inputs = [
            ReviewEmbeddingInput(review_id="r1", text="Test review text about music"),
            ReviewEmbeddingInput(review_id="r2", text="Another review about the app"),
        ]
        result = engine.embed(inputs)
        assert result["r1"].shape == (EMBEDDING_DIM,)
        assert result["r2"].shape == (EMBEDDING_DIM,)

    def test_same_text_similar_embeddings(self, engine):
        inputs = [
            ReviewEmbeddingInput(review_id="a", text="I love discovering music"),
            ReviewEmbeddingInput(review_id="b", text="I love discovering music"),
        ]
        result = engine.embed(inputs)
        diff = np.linalg.norm(result["a"] - result["b"])
        assert diff < 1e-4

    def test_different_texts_different_embeddings(self, engine):
        inputs = [
            ReviewEmbeddingInput(review_id="a", text="Music discovery algorithm is great"),
            ReviewEmbeddingInput(review_id="b", text="App crashes on startup every time"),
        ]
        result = engine.embed(inputs)
        diff = np.linalg.norm(result["a"] - result["b"])
        assert diff > 0.01  # TF-IDF vectors are in different directions

    def test_cache_param_accepted_but_bypassed(self, engine, tmp_path):
        # TF-IDF must fit on all texts at once; the cache param is accepted but not used
        from embeddings.embedding_cache import EmbeddingCache
        cache = EmbeddingCache(tmp_path / "cache")
        inputs = [
            ReviewEmbeddingInput(review_id="r1", text="review one about music"),
            ReviewEmbeddingInput(review_id="r2", text="review two about crashes"),
        ]
        result = engine.embed(inputs, cache=cache)
        # Results are returned regardless of cache state
        assert "r1" in result
        assert "r2" in result
        assert result["r1"].shape == (EMBEDDING_DIM,)
