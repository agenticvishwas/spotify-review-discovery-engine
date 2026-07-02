import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

import requests

from collectors.base import CollectorInterface
from models.raw_review import RawReview, make_stable_id

logger = logging.getLogger(__name__)

TWITTER_API_BASE = "https://api.twitter.com/2"
SEARCH_QUERIES = [
    "spotify recommend",
    "spotify discovery",
    "discover weekly",
    "spotify recommendations",
]
MIN_TEXT_LENGTH = 10
RATE_LIMIT_SECS = 1.0
REQUEST_TIMEOUT = 15
MAX_PER_REQUEST = 100


class SocialCollector(CollectorInterface):
    """Collects tweets via Twitter/X API v2 (requires Bearer Token)."""

    def __init__(self, bearer_token: str, batch_id: Optional[str] = None):
        self._bearer_token = bearer_token
        self._batch_id = batch_id or str(uuid.uuid4())
        self._session = requests.Session()
        self._session.headers.update({"Authorization": f"Bearer {bearer_token}"})

    def platform_name(self) -> str:
        return "social"

    def validate_credentials(self) -> bool:
        try:
            # Lightweight probe — check a known endpoint
            resp = self._session.get(
                f"{TWITTER_API_BASE}/tweets/search/recent",
                params={"query": "spotify", "max_results": 10},
                timeout=REQUEST_TIMEOUT,
            )
            return resp.status_code in (200, 429)  # 429 = valid token, just rate-limited
        except requests.RequestException as exc:
            logger.warning("Twitter/X credential validation failed: %s", exc)
            return False

    def fetch(
        self,
        query: str = "",
        limit: int = 500,
        since_date: Optional[datetime] = None,
    ) -> list[RawReview]:
        ingested_at = datetime.now(timezone.utc).isoformat()
        reviews: list[RawReview] = []
        search_list = [query] if query else SEARCH_QUERIES
        per_query = max(1, limit // len(search_list))

        for search_query in search_list:
            if len(reviews) >= limit:
                break
            batch = self._search(search_query, per_query, ingested_at, since_date)
            reviews.extend(batch)
            time.sleep(RATE_LIMIT_SECS)

        return reviews[:limit]

    def _search(
        self,
        query: str,
        limit: int,
        ingested_at: str,
        since_date: Optional[datetime],
    ) -> list[RawReview]:
        reviews: list[RawReview] = []
        next_token: Optional[str] = None
        full_query = f"({query}) lang:en -is:retweet"

        while len(reviews) < limit:
            params: dict = {
                "query": full_query,
                "max_results": min(MAX_PER_REQUEST, limit - len(reviews)),
                "tweet.fields": "created_at,author_id,text",
                "expansions": "author_id",
                "user.fields": "username",
            }
            if since_date:
                params["start_time"] = since_date.strftime("%Y-%m-%dT%H:%M:%SZ")
            if next_token:
                params["next_token"] = next_token

            try:
                resp = self._session.get(
                    f"{TWITTER_API_BASE}/tweets/search/recent",
                    params=params,
                    timeout=REQUEST_TIMEOUT,
                )
                if resp.status_code == 429:
                    logger.warning("Twitter rate limit hit; backing off 60s")
                    time.sleep(60)
                    continue
                resp.raise_for_status()
                data = resp.json()
            except requests.RequestException as exc:
                logger.warning("Twitter search failed for query '%s': %s", query, exc)
                break

            tweets = data.get("data", [])
            users = {
                u["id"]: u.get("username", u["id"])
                for u in data.get("includes", {}).get("users", [])
            }

            for tweet in tweets:
                text = tweet.get("text", "")
                if len(text) < MIN_TEXT_LENGTH:
                    continue

                author_id = tweet.get("author_id", "")
                author_name = users.get(author_id, author_id)
                created_at = tweet.get("created_at", "")
                tweet_id = tweet.get("id", "")

                reviews.append(RawReview(
                    id=make_stable_id("social", author_name, created_at, text),
                    source_platform="social",
                    raw_text=text,
                    rating=None,
                    author_id=author_name,
                    published_at=created_at,
                    source_url=f"https://twitter.com/i/web/status/{tweet_id}",
                    ingested_at=ingested_at,
                    ingestion_batch_id=self._batch_id,
                ))

            next_token = data.get("meta", {}).get("next_token")
            if not next_token or not tweets:
                break

            time.sleep(RATE_LIMIT_SECS)

        return reviews
