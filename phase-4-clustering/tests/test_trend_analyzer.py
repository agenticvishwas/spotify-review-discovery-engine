"""Unit tests for TrendAnalyzer."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from themes.trend_analyzer import TrendAnalyzer


def _dt(days_ago: int, reference: datetime) -> str:
    return (reference - timedelta(days=days_ago)).isoformat()


class TestTrendAnalyzer:
    @pytest.fixture
    def ref(self):
        return datetime(2026, 6, 30, tzinfo=timezone.utc)

    def test_increasing_trend(self, ref):
        # 20 reviews in last 90 days, 5 in prior 90 → +300% > +20%
        recent = {f"r_recent_{i}": _dt(i * 4, ref) for i in range(20)}  # 0–76 days ago
        prior = {f"r_prior_{i}": _dt(91 + i * 15, ref) for i in range(5)}  # 91–151 days ago
        date_lookup = {**recent, **prior}

        cluster = {"member_review_ids": list(date_lookup.keys())}
        analyzer = TrendAnalyzer(reference_date=ref)
        result = analyzer.analyze([cluster], date_lookup)[0]

        assert result["trend_direction"] == "increasing"
        assert result["trend_volume_change_pct"] > 0.20

    def test_decreasing_trend(self, ref):
        # 2 reviews in last 90 days, 20 in prior 90 → -90% < -20%
        recent = {f"r_recent_{i}": _dt(i * 40, ref) for i in range(2)}   # 0 and 40 days ago
        prior = {f"r_prior_{i}": _dt(91 + i * 4, ref) for i in range(20)}
        date_lookup = {**recent, **prior}

        cluster = {"member_review_ids": list(date_lookup.keys())}
        analyzer = TrendAnalyzer(reference_date=ref)
        result = analyzer.analyze([cluster], date_lookup)[0]

        assert result["trend_direction"] == "decreasing"
        assert result["trend_volume_change_pct"] < -0.20

    def test_stable_trend(self, ref):
        # Equal volume in both windows
        recent = {f"r_r_{i}": _dt(i * 8, ref) for i in range(10)}
        prior = {f"r_p_{i}": _dt(91 + i * 8, ref) for i in range(10)}
        date_lookup = {**recent, **prior}

        cluster = {"member_review_ids": list(date_lookup.keys())}
        analyzer = TrendAnalyzer(reference_date=ref)
        result = analyzer.analyze([cluster], date_lookup)[0]

        assert result["trend_direction"] == "stable"
        assert abs(result["trend_volume_change_pct"]) <= 0.20

    def test_no_dates_returns_stable(self, ref):
        cluster = {"member_review_ids": ["r1", "r2"]}
        analyzer = TrendAnalyzer(reference_date=ref)
        result = analyzer.analyze([cluster], {})[0]
        assert result["trend_direction"] == "stable"
        assert result["trend_volume_change_pct"] == 0.0

    def test_all_recent_returns_increasing(self, ref):
        date_lookup = {f"r{i}": _dt(i * 5, ref) for i in range(10)}
        cluster = {"member_review_ids": list(date_lookup.keys())}
        analyzer = TrendAnalyzer(reference_date=ref)
        result = analyzer.analyze([cluster], date_lookup)[0]
        assert result["trend_direction"] == "increasing"

    def test_z_suffix_dates_parsed(self, ref):
        date_str = (ref - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
        date_lookup = {"r1": date_str}
        cluster = {"member_review_ids": ["r1"]}
        analyzer = TrendAnalyzer(reference_date=ref)
        result = analyzer.analyze([cluster], date_lookup)[0]
        assert result["trend_direction"] in ("increasing", "stable", "decreasing")

    def test_multiple_clusters_analyzed_independently(self, ref):
        # Cluster A: increasing, Cluster B: decreasing
        date_lookup_a = {f"a_{i}": _dt(i * 4, ref) for i in range(20)}
        date_lookup_a.update({f"a_p_{i}": _dt(91 + i * 20, ref) for i in range(3)})

        date_lookup_b = {f"b_{i}": _dt(i * 40, ref) for i in range(2)}
        date_lookup_b.update({f"b_p_{i}": _dt(91 + i * 4, ref) for i in range(20)})

        combined = {**date_lookup_a, **date_lookup_b}
        clusters = [
            {"member_review_ids": list(date_lookup_a.keys())},
            {"member_review_ids": list(date_lookup_b.keys())},
        ]
        analyzer = TrendAnalyzer(reference_date=ref)
        results = analyzer.analyze(clusters, combined)

        assert results[0]["trend_direction"] == "increasing"
        assert results[1]["trend_direction"] == "decreasing"
