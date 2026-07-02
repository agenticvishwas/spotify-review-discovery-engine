import pytest
from deduplication.exact_deduplicator import ExactDeduplicator
from deduplication.near_dup_detector import NearDupDetector


class TestExactDeduplicator:
    def setup_method(self):
        self.dedup = ExactDeduplicator()

    def test_new_text_not_duplicate(self):
        is_dup, canonical = self.dedup.is_duplicate("This is a unique review text.")
        assert is_dup is False
        assert canonical is None

    def test_same_text_is_duplicate_after_register(self):
        text = "Spotify is the best music app ever."
        self.dedup.register(text, "review-001")
        is_dup, canonical = self.dedup.is_duplicate(text)
        assert is_dup is True
        assert canonical == "review-001"

    def test_case_insensitive_matching(self):
        self.dedup.register("spotify is great", "review-001")
        is_dup, canonical = self.dedup.is_duplicate("SPOTIFY IS GREAT")
        assert is_dup is True
        assert canonical == "review-001"

    def test_whitespace_normalized_before_hashing(self):
        self.dedup.register("  spotify is great  ", "review-001")
        is_dup, canonical = self.dedup.is_duplicate("spotify is great")
        assert is_dup is True

    def test_register_twice_does_not_overwrite_canonical(self):
        text = "Great app."
        self.dedup.register(text, "review-001")
        self.dedup.register(text, "review-002")
        _, canonical = self.dedup.is_duplicate(text)
        assert canonical == "review-001"

    def test_different_texts_not_duplicates(self):
        self.dedup.register("I love Spotify", "review-001")
        is_dup, _ = self.dedup.is_duplicate("I hate Spotify")
        assert is_dup is False

    def test_empty_deduplicator_has_no_seen(self):
        dedup = ExactDeduplicator()
        is_dup, _ = dedup.is_duplicate("any text")
        assert is_dup is False

    def test_hash_is_deterministic(self):
        text = "Deterministic hashing test."
        h1 = ExactDeduplicator._hash(text)
        h2 = ExactDeduplicator._hash(text)
        assert h1 == h2

    def test_save_and_reload_index(self, tmp_path):
        index_path = tmp_path / "exact_hashes.json"
        dedup1 = ExactDeduplicator(index_path=index_path)
        dedup1.register("hello world", "review-001")
        dedup1.save_index()

        dedup2 = ExactDeduplicator(index_path=index_path)
        is_dup, canonical = dedup2.is_duplicate("hello world")
        assert is_dup is True
        assert canonical == "review-001"


class TestNearDupDetector:
    def setup_method(self):
        self.detector = NearDupDetector()

    def test_unique_text_not_near_dup(self):
        text = "Spotify has a great discover weekly playlist feature."
        self.detector.register(text, "review-001")
        is_dup, canonical = self.detector.is_near_duplicate(
            "I am reviewing a completely different topic about weather."
        )
        assert is_dup is False

    def test_identical_text_is_near_dup(self):
        text = "Spotify is amazing and I love the discover weekly."
        self.detector.register(text, "review-001")
        is_dup, canonical = self.detector.is_near_duplicate(text)
        assert is_dup is True
        assert canonical == "review-001"

    def test_slightly_modified_text_is_near_dup(self):
        # 18 shared tokens out of 20 total → Jaccard ~0.90, well above 0.85 threshold
        original = (
            "The Spotify app is great and the discover weekly playlist feature has been "
            "amazing for my music listening experience every single day"
        )
        slight_mod = (
            "The Spotify app is great and the discover weekly playlist feature has been "
            "amazing for my music streaming experience every single day"
        )
        self.detector.register(original, "review-001")
        is_dup, canonical = self.detector.is_near_duplicate(slight_mod)
        assert is_dup is True

    def test_register_is_idempotent(self):
        text = "Great app for music streaming."
        self.detector.register(text, "review-001")
        self.detector.register(text, "review-001")  # should not raise
