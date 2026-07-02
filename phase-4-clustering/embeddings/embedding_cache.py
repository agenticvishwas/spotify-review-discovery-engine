"""File-based embedding cache: one .npy file per review_id."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


class EmbeddingCache:
    def __init__(self, cache_dir: Path):
        self._dir = Path(cache_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def get(self, review_id: str) -> Optional[np.ndarray]:
        path = self._npy(review_id)
        if path.exists():
            return np.load(str(path))
        return None

    def put(self, review_id: str, embedding: np.ndarray, model: str) -> None:
        path = self._npy(review_id)
        np.save(str(path), embedding)
        path.with_suffix(".json").write_text(
            json.dumps({
                "review_id": review_id,
                "model": model,
                "embedded_at": datetime.now(timezone.utc).isoformat(),
                "shape": list(embedding.shape),
            }),
            encoding="utf-8",
        )

    def exists(self, review_id: str) -> bool:
        return self._npy(review_id).exists()

    def count(self) -> int:
        return sum(1 for _ in self._dir.glob("*.npy"))

    def _npy(self, review_id: str) -> Path:
        return self._dir / f"{review_id}.npy"
