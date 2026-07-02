import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

import requests

from collectors.base import CollectorInterface
from models.raw_review import RawReview, make_stable_id

logger = logging.getLogger(__name__)

SPOTIFY_APP_ID = "324684580"
RSS_URL = (
    "https://itunes.apple.com/us/rss/customerreviews"
    "/page={page}/id={app_id}/sortby=mostrecent/json"
)
MAX_PAGES = 10       # iTunes RSS caps at 10 pages × 50 reviews = 500 max
RATE_LIMIT_SECS = 1.0
REQUEST_TIMEOUT = 15


def _exponential_backoff(attempt: int, base: float = 2.0) -> float:
    return base ** attempt


class AppStoreCollector(CollectorInterface):
    def __init__(
        self,
        app_id: str = SPOTIFY_APP_ID,
        batch_id: Optional[str] = None,
        session: Optional[requests.Session] = None,
    ):
        self._app_id = app_id
        self._batch_id = batch_id or str(uuid.uuid4())
        self._session = session or requests.Session()
        self._session.headers.update({"Accept": "application/json"})

    def platform_name(self) -> str:
        return "app_store"

    def validate_credentials(self) -> bool:
        url = RSS_URL.format(page=1, app_id=self._app_id)
        try:
            resp = self._session.get(url, timeout=REQUEST_TIMEOUT)
            return resp.status_code == 200
        except requests.RequestException as exc:
            logger.warning("App Store connectivity check failed: %s", exc)
            return False

    def fetch(
        self,
        query: str = "",
        limit: int = 500,
        since_date: Optional[datetime] = None,
    ) -> list[RawReview]:
        ingested_at = datetime.now(timezone.utc).isoformat()
        reviews: list[RawReview] = []

        for page in range(1, MAX_PAGES + 1):
            if len(reviews) >= limit:
                break

            url = RSS_URL.format(page=page, app_id=self._app_id)
            page_reviews = self._fetch_page_with_retry(url, ingested_at, since_date)

            if not page_reviews:
                break  # iTunes returns empty feed when page exceeds available data

            reviews.extend(page_reviews)
            time.sleep(RATE_LIMIT_SECS)

        return reviews[:limit]

    def _fetch_page_with_retry(
        self,
        url: str,
        ingested_at: str,
        since_date: Optional[datetime],
        max_retries: int = 3,
    ) -> list[RawReview]:
        for attempt in range(max_retries):
            try:
                resp = self._session.get(url, timeout=REQUEST_TIMEOUT)
                resp.raise_for_status()
                return self._parse_feed(resp.json(), ingested_at, since_date)
            except requests.HTTPError as exc:
                if exc.response is not None and exc.response.status_code == 429:
                    delay = _exponential_backoff(attempt)
                    logger.warning("App Store rate-limited. Backing off %.1fs (attempt %d)", delay, attempt + 1)
                    time.sleep(delay)
                else:
                    logger.warning("App Store HTTP error: %s", exc)
                    break
            except (requests.RequestException, ValueError) as exc:
                logger.warning("App Store fetch attempt %d failed: %s", attempt + 1, exc)
                if attempt < max_retries - 1:
                    time.sleep(30)
        return []

    def _parse_feed(
        self,
        data: dict,
        ingested_at: str,
        since_date: Optional[datetime],
    ) -> list[RawReview]:
        entries = data.get("feed", {}).get("entry", [])
        if not entries:
            return []

        # Page 1 includes an app-info entry as the first item (no im:rating field)
        if entries and "im:rating" not in entries[0]:
            entries = entries[1:]

        reviews: list[RawReview] = []
        for entry in entries:
            review = self._parse_entry(entry, ingested_at)
            if review is None:
                continue
            if since_date and _is_before(review.published_at, since_date):
                continue
            reviews.append(review)

        return reviews

    def _parse_entry(self, entry: dict, ingested_at: str) -> Optional[RawReview]:
        try:
            title = entry.get("title", {}).get("label", "")
            body = entry.get("content", {}).get("label", "")
            raw_text = f"{title}\n{body}".strip() if title else body.strip()
            if not raw_text:
                return None

            rating_label = entry.get("im:rating", {}).get("label")
            rating = int(rating_label) if rating_label and rating_label.isdigit() else None

            author = entry.get("author", {}).get("name", {}).get("label") or None
            published_at = entry.get("updated", {}).get("label", "")
            source_url = (
                entry.get("link", {}).get("attributes", {}).get("href")
                or f"https://apps.apple.com/app/id{self._app_id}"
            )

            return RawReview(
                id=make_stable_id("app_store", author, published_at, raw_text),
                source_platform="app_store",
                raw_text=raw_text,
                rating=rating,
                author_id=author,
                published_at=published_at,
                source_url=source_url,
                ingested_at=ingested_at,
                ingestion_batch_id=self._batch_id,
            )
        except Exception as exc:
            logger.debug("Skipping malformed App Store entry: %s", exc)
            return None


def _is_before(published_at: str, since_date: datetime) -> bool:
    try:
        pub = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        aware_since = since_date if since_date.tzinfo else since_date.replace(tzinfo=timezone.utc)
        return pub < aware_since
    except ValueError:
        return False
