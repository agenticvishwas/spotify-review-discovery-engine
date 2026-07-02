"""Trend detection: compares cluster volume in last 90 days vs prior 90 days."""

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

INCREASING_THRESHOLD = 0.20   # +20%
DECREASING_THRESHOLD = -0.20  # -20%
TREND_WINDOW_DAYS = 90


class TrendAnalyzer:
    """Classifies each cluster's volume trend as increasing, stable, or decreasing."""

    def __init__(
        self,
        window_days: int = TREND_WINDOW_DAYS,
        reference_date: Optional[datetime] = None,
    ):
        self._window_days = window_days
        self._reference_date = reference_date or datetime.now(timezone.utc)

    def analyze(
        self,
        clusters: list[dict],
        review_date_lookup: dict[str, str],
    ) -> list[dict]:
        """Return updated cluster dicts with trend_direction and trend_volume_change_pct."""
        updated = []
        for cluster in clusters:
            trend, pct = self._compute_trend(cluster["member_review_ids"], review_date_lookup)
            updated.append({
                **cluster,
                "trend_direction": trend,
                "trend_volume_change_pct": round(pct, 4),
            })
        return updated

    def _compute_trend(
        self,
        member_ids: list[str],
        review_date_lookup: dict[str, str],
    ) -> tuple[str, float]:
        """Return (direction, pct_change) for a cluster's review volume."""
        cutoff_recent = self._reference_date
        cutoff_prior = cutoff_recent - timedelta(days=self._window_days)
        cutoff_old = cutoff_prior - timedelta(days=self._window_days)

        recent_count = 0
        prior_count = 0

        for rid in member_ids:
            date_str = review_date_lookup.get(rid)
            if not date_str:
                continue
            try:
                dt = self._parse_date(date_str)
            except ValueError:
                continue

            if cutoff_prior <= dt < cutoff_recent:
                recent_count += 1
            elif cutoff_old <= dt < cutoff_prior:
                prior_count += 1

        if prior_count == 0 and recent_count == 0:
            return "stable", 0.0

        if prior_count == 0:
            # All volume is in recent window — treat as strongly increasing
            return "increasing", 1.0

        pct_change = (recent_count - prior_count) / prior_count

        if pct_change > INCREASING_THRESHOLD:
            direction = "increasing"
        elif pct_change < DECREASING_THRESHOLD:
            direction = "decreasing"
        else:
            direction = "stable"

        return direction, pct_change

    @staticmethod
    def _parse_date(date_str: str) -> datetime:
        """Parse ISO8601 string to timezone-aware datetime."""
        # Handle 'Z' suffix and naive datetimes
        if date_str.endswith("Z"):
            date_str = date_str[:-1] + "+00:00"
        dt = datetime.fromisoformat(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
