import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from collectors.base import CollectorInterface
from models.raw_review import RawReview, make_stable_id

logger = logging.getLogger(__name__)

SPOTIFY_PACKAGE = "com.spotify.music"
RATE_LIMIT_SECS = 2.0
BATCH_SIZE = 200  # google-play-scraper max per call


class GooglePlayCollector(CollectorInterface):
    def __init__(
        self,
        package: str = SPOTIFY_PACKAGE,
        batch_id: Optional[str] = None,
        country: str = "us",
        lang: str = "en",
    ):
        self._package = package
        self._batch_id = batch_id or str(uuid.uuid4())
        self._country = country
        self._lang = lang

    def platform_name(self) -> str:
        return "google_play"

    def validate_credentials(self) -> bool:
        # No credentials needed — validates the package exists
        try:
            from google_play_scraper import app as gp_app
            result = gp_app(self._package, lang=self._lang, country=self._country)
            return bool(result.get("title"))
        except ImportError:
            logger.error("google-play-scraper not installed: pip install google-play-scraper")
            return False
        except Exception as exc:
            logger.warning("Google Play connectivity check failed: %s", exc)
            return False

    def fetch(
        self,
        query: str = "",
        limit: int = 500,
        since_date: Optional[datetime] = None,
    ) -> list[RawReview]:
        try:
            from google_play_scraper import reviews as gp_reviews, Sort
        except ImportError:
            logger.error("google-play-scraper not installed: pip install google-play-scraper")
            return []

        ingested_at = datetime.now(timezone.utc).isoformat()
        reviews: list[RawReview] = []
        continuation_token = None

        while len(reviews) < limit:
            fetch_count = min(BATCH_SIZE, limit - len(reviews))
            try:
                result, continuation_token = gp_reviews(
                    self._package,
                    lang=self._lang,
                    country=self._country,
                    sort=Sort.NEWEST,
                    count=fetch_count,
                    continuation_token=continuation_token,
                )
            except Exception as exc:
                logger.warning("Google Play fetch failed: %s", exc)
                break

            if not result:
                break

            passed_since_date = False
            for entry in result:
                if since_date:
                    pub = entry.get("at")
                    if pub:
                        aware_pub = pub.replace(tzinfo=timezone.utc) if pub.tzinfo is None else pub
                        aware_since = since_date if since_date.tzinfo else since_date.replace(tzinfo=timezone.utc)
                        if aware_pub < aware_since:
                            # Results are sorted newest-first: once we hit an entry
                            # older than since_date, all remaining entries will be too.
                            passed_since_date = True
                            break

                review = self._parse_entry(entry, ingested_at)
                if review is not None:
                    reviews.append(review)

            if passed_since_date or not continuation_token:
                break

            time.sleep(RATE_LIMIT_SECS)

        return reviews[:limit]

    def _parse_entry(self, entry: dict, ingested_at: str) -> Optional[RawReview]:
        try:
            content = (entry.get("content") or "").strip()
            if not content:
                return None

            author = entry.get("userName") or None
            rating = entry.get("score")
            published = entry.get("at")
            published_str = published.isoformat() if published else ""
            review_id_str = entry.get("reviewId", "")
            source_url = (
                f"https://play.google.com/store/apps/details"
                f"?id={self._package}&reviewId={review_id_str}"
            )

            return RawReview(
                id=make_stable_id("google_play", author, published_str, content),
                source_platform="google_play",
                raw_text=content,
                rating=rating,
                author_id=author,
                published_at=published_str,
                source_url=source_url,
                ingested_at=ingested_at,
                ingestion_batch_id=self._batch_id,
            )
        except Exception as exc:
            logger.debug("Skipping malformed Google Play entry: %s", exc)
            return None
