import pytest
from normalizers.rating_normalizer import RatingNormalizer
from normalizers.date_normalizer import DateNormalizer
from normalizers.platform_mapper import PlatformMapper


class TestRatingNormalizer:
    def setup_method(self):
        self.norm = RatingNormalizer()

    def test_app_store_integer_to_float(self):
        assert self.norm.normalize(5, "app_store") == 5.0
        assert self.norm.normalize(1, "app_store") == 1.0
        assert self.norm.normalize(3, "app_store") == 3.0

    def test_google_play_integer_to_float(self):
        assert self.norm.normalize(4, "google_play") == 4.0

    def test_reddit_returns_none(self):
        assert self.norm.normalize(100, "reddit") is None

    def test_community_returns_none(self):
        assert self.norm.normalize(5, "community") is None

    def test_social_returns_none(self):
        assert self.norm.normalize(5, "social") is None

    def test_none_rating_returns_none(self):
        assert self.norm.normalize(None, "app_store") is None

    def test_clamps_out_of_range_rating(self):
        assert self.norm.normalize(6, "app_store") == 5.0
        assert self.norm.normalize(0, "app_store") == 1.0

    def test_returns_float_type(self):
        result = self.norm.normalize(4, "app_store")
        assert isinstance(result, float)


class TestDateNormalizer:
    def setup_method(self):
        self.norm = DateNormalizer()

    def test_iso8601_with_z(self):
        result = self.norm.normalize("2024-01-15T10:30:00Z")
        assert "+00:00" in result or result.endswith("Z") or "UTC" in result
        assert "2024-01-15" in result

    def test_iso8601_with_offset(self):
        result = self.norm.normalize("2024-01-15T10:30:00+05:30")
        assert "2024-01-15" in result

    def test_date_only(self):
        result = self.norm.normalize("2024-01-15")
        assert "2024-01-15" in result

    def test_datetime_no_timezone(self):
        result = self.norm.normalize("2024-01-15 10:30:00")
        assert "2024-01-15" in result

    def test_empty_string_returned_unchanged(self):
        assert self.norm.normalize("") == ""

    def test_unparseable_string_returned_unchanged(self):
        bad = "not-a-date"
        assert self.norm.normalize(bad) == bad

    def test_normalizes_to_utc(self):
        # +05:30 offset → UTC should shift hours
        result = self.norm.normalize("2024-01-15T10:30:00+05:30")
        assert "05:00:00+00:00" in result


class TestPlatformMapper:
    def setup_method(self):
        self.mapper = PlatformMapper()

    def test_canonical_values_unchanged(self):
        for p in ("app_store", "google_play", "reddit", "community", "social"):
            assert self.mapper.map(p) == p

    def test_appstore_alias(self):
        assert self.mapper.map("appstore") == "app_store"
        assert self.mapper.map("apple") == "app_store"

    def test_googleplay_alias(self):
        assert self.mapper.map("googleplay") == "google_play"
        assert self.mapper.map("play_store") == "google_play"

    def test_case_insensitive(self):
        assert self.mapper.map("App_Store") == "app_store"
        assert self.mapper.map("GOOGLE_PLAY") == "google_play"

    def test_unknown_platform_passthrough(self):
        assert self.mapper.map("unknown_platform") == "unknown_platform"
