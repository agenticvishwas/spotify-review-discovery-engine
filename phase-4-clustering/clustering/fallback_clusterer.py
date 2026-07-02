"""k-means fallback that assigns HDBSCAN noise points to pseudo-clusters."""

import logging

import numpy as np

logger = logging.getLogger(__name__)

FALLBACK_K = 5


class FallbackClusterer:
    """Reassigns noise points (-1 labels) via k-means to avoid discarding them."""

    def __init__(self, k: int = FALLBACK_K):
        self._k = k

    def assign(self, embeddings: np.ndarray, labels: np.ndarray) -> np.ndarray:
        """Return updated labels where all -1 entries are replaced with fallback IDs.

        Fallback cluster IDs start immediately after the highest HDBSCAN cluster ID,
        so they never collide with existing cluster labels.
        """
        noise_mask = labels == -1
        n_noise = int(noise_mask.sum())
        if n_noise == 0:
            return labels.copy()

        noise_embeddings = embeddings[noise_mask]
        k = min(self._k, n_noise)
        max_existing = int(labels[~noise_mask].max()) if (~noise_mask).any() else -1

        from sklearn.cluster import KMeans  # lazy import

        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        fallback_labels = kmeans.fit_predict(noise_embeddings) + max_existing + 1

        updated = labels.copy()
        updated[noise_mask] = fallback_labels

        logger.info(
            "phase=4 action=fallback_complete noise=%d reassigned_into=%d_clusters offset=%d",
            n_noise,
            k,
            max_existing + 1,
        )
        return updated
