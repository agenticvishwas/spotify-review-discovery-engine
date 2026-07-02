"""HDBSCAN clustering — primary algorithm for grouping review embeddings."""

import logging

import numpy as np

logger = logging.getLogger(__name__)

HDBSCAN_MIN_CLUSTER_SIZE = 10
HDBSCAN_MIN_SAMPLES = 5


class HDBSCANClusterer:
    """Density-based clustering that handles variable cluster sizes and marks outliers."""

    def __init__(
        self,
        min_cluster_size: int = HDBSCAN_MIN_CLUSTER_SIZE,
        min_samples: int = HDBSCAN_MIN_SAMPLES,
    ):
        self._min_cluster_size = min_cluster_size
        self._min_samples = min_samples

    def fit(self, embeddings: np.ndarray) -> np.ndarray:
        """Cluster embeddings. Returns integer label array; -1 = noise point."""
        import hdbscan  # lazy import

        min_cluster_size = min(self._min_cluster_size, max(2, len(embeddings) // 5))
        min_samples = min(self._min_samples, min_cluster_size)

        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=min_cluster_size,
            min_samples=min_samples,
            metric="euclidean",
            cluster_selection_method="eom",
        )
        labels: np.ndarray = clusterer.fit_predict(embeddings)

        n_clusters = int(len(set(labels)) - (1 if -1 in labels else 0))
        n_noise = int((labels == -1).sum())
        logger.info(
            "phase=4 action=hdbscan_complete clusters=%d noise=%d noise_rate=%.3f",
            n_clusters,
            n_noise,
            n_noise / max(1, len(labels)),
        )
        return labels
