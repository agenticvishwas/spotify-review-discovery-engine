"""Embedding engine using TF-IDF + TruncatedSVD (scikit-learn only, no torch/onnx).

This backend works on Python 3.14 without Visual C++ Redistributable or CUDA.
All embeddings are computed in one call so the TF-IDF vocabulary is consistent
across the corpus — the file cache is therefore not used for this backend.

When Python 3.12 + sentence-transformers becomes available, swap _fit_transform()
for a transformer model without changing any other code.
"""

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "tfidf-svd"
EMBEDDING_DIM = 384
BATCH_SIZE = 64  # kept for API compatibility; TF-IDF processes all at once


@dataclass
class ReviewEmbeddingInput:
    review_id: str
    text: str


class EmbeddingEngine:
    """TF-IDF + SVD embeddings — produces 384-dim L2-normalised vectors.

    TF-IDF must be fit on the full corpus to keep all embeddings in the same
    vector space.  The file-based cache is intentionally bypassed: a re-fit on
    stale vocabulary would make cached and new embeddings incomparable.
    """

    def __init__(self, model_name: str = EMBEDDING_MODEL, n_components: int = EMBEDDING_DIM):
        self._model_name = model_name
        self._n_components = n_components

    def embed(
        self,
        inputs: list[ReviewEmbeddingInput],
        cache: Optional[object] = None,  # accepted but unused for TF-IDF
    ) -> dict[str, np.ndarray]:
        """Return {review_id: embedding_vector} for all inputs."""
        if not inputs:
            return {}

        texts = [inp.text for inp in inputs]
        vecs = self._fit_transform(texts)

        result: dict[str, np.ndarray] = {}
        for inp, vec in zip(inputs, vecs):
            result[inp.review_id] = vec

        logger.info(
            "phase=4 action=embed_complete total=%d model=%s dim=%d",
            len(inputs), self._model_name, vecs.shape[1],
        )
        return result

    def _fit_transform(self, texts: list[str]) -> np.ndarray:
        """Fit TF-IDF on the corpus, reduce with SVD, L2-normalise."""
        from sklearn.decomposition import TruncatedSVD
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.preprocessing import normalize

        vectorizer = TfidfVectorizer(
            max_features=20_000,
            sublinear_tf=True,
            min_df=1,
            ngram_range=(1, 2),
        )
        tfidf = vectorizer.fit_transform(texts)

        n_components = max(1, min(self._n_components, len(texts) - 1, tfidf.shape[1]))
        svd = TruncatedSVD(n_components=n_components, random_state=42)
        reduced = svd.fit_transform(tfidf)

        normalised = normalize(reduced, norm="l2").astype(np.float32)

        # Pad to EMBEDDING_DIM when corpus is very small
        if normalised.shape[1] < self._n_components:
            pad = np.zeros(
                (normalised.shape[0], self._n_components - normalised.shape[1]),
                dtype=np.float32,
            )
            normalised = np.hstack([normalised, pad])

        return normalised

    @staticmethod
    def build_text(
        clean_text: Optional[str],
        jtbd_signal: Optional[str],
        primary_complaint: Optional[str],
        primary_praise: Optional[str] = None,
        user_intent: Optional[str] = None,
        feature_mentions: Optional[list[str]] = None,
    ) -> str:
        """Construct a rich text string for embedding from available review fields."""
        parts = []
        if clean_text:
            parts.append(clean_text)
        if jtbd_signal:
            parts.append(jtbd_signal)
        if primary_complaint:
            parts.append(primary_complaint)
        if primary_praise:
            parts.append(primary_praise)
        if user_intent:
            parts.append(user_intent)
        if feature_mentions:
            parts.append(" ".join(feature_mentions))
        return " ".join(p.strip() for p in parts if p.strip())
