"""UMAP dimensionality reduction for improved clustering quality."""

import logging

import numpy as np

logger = logging.getLogger(__name__)

UMAP_N_COMPONENTS = 50
UMAP_N_NEIGHBORS = 15
UMAP_MIN_DIST = 0.1
UMAP_METRIC = "cosine"
UMAP_RANDOM_STATE = 42


class UMAPReducer:
    def __init__(
        self,
        n_components: int = UMAP_N_COMPONENTS,
        n_neighbors: int = UMAP_N_NEIGHBORS,
        min_dist: float = UMAP_MIN_DIST,
        metric: str = UMAP_METRIC,
        random_state: int = UMAP_RANDOM_STATE,
    ):
        self._n_components = n_components
        self._n_neighbors = n_neighbors
        self._min_dist = min_dist
        self._metric = metric
        self._random_state = random_state

    def fit_transform(self, embeddings: np.ndarray) -> np.ndarray:
        """Reduce high-dimensional embeddings to n_components dimensions.

        Automatically clamps n_neighbors and n_components when corpus is small.
        """
        import umap  # lazy import — heavy dep

        n = embeddings.shape[0]
        n_neighbors = min(self._n_neighbors, max(2, n - 1))
        n_components = min(self._n_components, n - 1, embeddings.shape[1])

        if n_neighbors != self._n_neighbors:
            logger.warning(
                "phase=4 action=umap_clamp n_samples=%d n_neighbors clamped %d→%d",
                n, self._n_neighbors, n_neighbors,
            )

        reducer = umap.UMAP(
            n_components=n_components,
            n_neighbors=n_neighbors,
            min_dist=self._min_dist,
            metric=self._metric,
            random_state=self._random_state,
        )
        reduced = reducer.fit_transform(embeddings)
        logger.info("phase=4 action=umap_complete shape=%s→%s", embeddings.shape, reduced.shape)
        return reduced
