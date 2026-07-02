"""Unit tests for HDBSCANClusterer and FallbackClusterer."""

import sys
from pathlib import Path
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from clustering.hdbscan_clusterer import HDBSCANClusterer
from clustering.fallback_clusterer import FallbackClusterer


def make_cluster_data(n_clusters: int = 3, points_per_cluster: int = 20, noise: int = 5, seed: int = 42) -> np.ndarray:
    """Synthetic blobs for deterministic clustering tests."""
    rng = np.random.default_rng(seed)
    centers = rng.uniform(-10, 10, size=(n_clusters, 10))
    data = []
    for center in centers:
        pts = rng.normal(loc=center, scale=0.5, size=(points_per_cluster, 10))
        data.append(pts)
    if noise > 0:
        data.append(rng.uniform(-15, 15, size=(noise, 10)))
    return np.vstack(data)


class TestHDBSCANClusterer:
    def test_returns_label_array_correct_length(self):
        data = make_cluster_data()
        clusterer = HDBSCANClusterer(min_cluster_size=5, min_samples=3)
        labels = clusterer.fit(data)
        assert len(labels) == len(data)

    def test_detects_multiple_clusters(self):
        data = make_cluster_data(n_clusters=3, points_per_cluster=30, noise=0)
        clusterer = HDBSCANClusterer(min_cluster_size=5, min_samples=3)
        labels = clusterer.fit(data)
        n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
        assert n_clusters >= 2

    def test_labels_are_integers(self):
        data = make_cluster_data()
        clusterer = HDBSCANClusterer(min_cluster_size=5, min_samples=3)
        labels = clusterer.fit(data)
        assert labels.dtype in (np.int32, np.int64, np.intp)

    def test_handles_tiny_corpus(self):
        data = np.random.default_rng(0).normal(size=(12, 5))
        clusterer = HDBSCANClusterer(min_cluster_size=5, min_samples=3)
        labels = clusterer.fit(data)
        assert len(labels) == 12


class TestFallbackClusterer:
    def test_no_noise_returns_unchanged(self):
        labels = np.array([0, 0, 1, 1, 2, 2])
        embeddings = np.random.default_rng(0).normal(size=(6, 10))
        fallback = FallbackClusterer(k=3)
        updated = fallback.assign(embeddings, labels)
        np.testing.assert_array_equal(updated, labels)

    def test_noise_points_reassigned(self):
        labels = np.array([0, 0, -1, -1, 1])
        embeddings = np.random.default_rng(0).normal(size=(5, 10))
        fallback = FallbackClusterer(k=2)
        updated = fallback.assign(embeddings, labels)
        assert -1 not in updated

    def test_fallback_ids_dont_overlap_existing(self):
        labels = np.array([0, 1, 2, -1, -1])
        embeddings = np.random.default_rng(0).normal(size=(5, 10))
        fallback = FallbackClusterer(k=2)
        updated = fallback.assign(embeddings, labels)
        # Original cluster IDs 0,1,2 must still exist unchanged
        assert updated[0] == 0
        assert updated[1] == 1
        assert updated[2] == 2
        # Fallback IDs must be >= 3
        for i in [3, 4]:
            assert updated[i] >= 3

    def test_k_clamped_when_fewer_noise_than_k(self):
        labels = np.array([0, 0, -1])  # only 1 noise point
        embeddings = np.random.default_rng(0).normal(size=(3, 5))
        fallback = FallbackClusterer(k=5)
        updated = fallback.assign(embeddings, labels)
        assert -1 not in updated
