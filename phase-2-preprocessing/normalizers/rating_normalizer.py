from typing import Optional

_NO_RATING_PLATFORMS = frozenset({"reddit", "community", "social"})


class RatingNormalizer:
    """Normalize platform-specific ratings to a 1.0–5.0 float scale.

    Platforms without a star-rating system (Reddit, Community, Social) return null.
    """

    def normalize(self, rating: Optional[int], platform: str) -> Optional[float]:
        if platform in _NO_RATING_PLATFORMS or rating is None:
            return None
        return float(max(1, min(5, rating)))
