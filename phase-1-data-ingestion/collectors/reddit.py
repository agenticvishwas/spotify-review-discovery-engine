import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from collectors.base import CollectorInterface
from models.raw_review import RawReview, make_stable_id

logger = logging.getLogger(__name__)

TARGET_SUBREDDITS = ["spotify", "SpotifyTheftClaims", "Music"]
SEARCH_KEYWORDS = [
    '"discovery"',
    '"recommend"',
    '"repetitive"',
    '"same songs"',
    '"Discover Weekly"',
]
DEFAULT_QUERY = " OR ".join(SEARCH_KEYWORDS)
RATE_LIMIT_SECS = 1.0
MAX_POSTS_PER_SUB = 100


class RedditCollector(CollectorInterface):
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        user_agent: str = "spotify-review-collector/1.0 (by /u/research-bot)",
        batch_id: Optional[str] = None,
    ):
        self._client_id = client_id
        self._client_secret = client_secret
        self._user_agent = user_agent
        self._batch_id = batch_id or str(uuid.uuid4())
        self._reddit = None  # lazy-initialized

    def platform_name(self) -> str:
        return "reddit"

    def validate_credentials(self) -> bool:
        try:
            reddit = self._get_client()
            # A cheap read-only probe: fetch subreddit info
            sub = reddit.subreddit("spotify")
            _ = sub.id
            return True
        except Exception as exc:
            logger.error("Reddit credential validation failed: %s", exc)
            return False

    def fetch(
        self,
        query: str = "",
        limit: int = 500,
        since_date: Optional[datetime] = None,
    ) -> list[RawReview]:
        reddit = self._get_client()
        ingested_at = datetime.now(timezone.utc).isoformat()
        search_query = query or DEFAULT_QUERY
        reviews: list[RawReview] = []

        per_sub_limit = max(1, limit // len(TARGET_SUBREDDITS))

        for sub_name in TARGET_SUBREDDITS:
            if len(reviews) >= limit:
                break
            batch = self._fetch_subreddit(
                reddit, sub_name, search_query, per_sub_limit, ingested_at, since_date
            )
            reviews.extend(batch)
            time.sleep(RATE_LIMIT_SECS)

        return reviews[:limit]

    def _fetch_subreddit(
        self,
        reddit,
        sub_name: str,
        query: str,
        limit: int,
        ingested_at: str,
        since_date: Optional[datetime],
    ) -> list[RawReview]:
        try:
            subreddit = reddit.subreddit(sub_name)
            posts = list(subreddit.search(query, sort="new", limit=min(limit, MAX_POSTS_PER_SUB)))
        except Exception as exc:
            logger.warning("Reddit fetch failed for r/%s: %s", sub_name, exc)
            return []

        reviews: list[RawReview] = []

        for post in posts:
            post_time = datetime.fromtimestamp(post.created_utc, tz=timezone.utc)
            aware_since = (
                since_date.replace(tzinfo=timezone.utc) if since_date and not since_date.tzinfo
                else since_date
            )
            if aware_since and post_time < aware_since:
                continue

            # Post body (selftext)
            if post.selftext and post.selftext.strip() not in ("", "[deleted]", "[removed]"):
                review = self._post_to_review(post, ingested_at)
                if review:
                    reviews.append(review)

            # Top-level comments
            try:
                post.comments.replace_more(limit=0)
                for comment in post.comments.list():
                    body = comment.body or ""
                    if body.strip() in ("", "[deleted]", "[removed]"):
                        continue
                    c_time = datetime.fromtimestamp(comment.created_utc, tz=timezone.utc)
                    if aware_since and c_time < aware_since:
                        continue
                    review = self._comment_to_review(comment, post, ingested_at)
                    if review:
                        reviews.append(review)
            except Exception as exc:
                logger.debug("Failed to load comments for post %s: %s", post.id, exc)

        return reviews

    def _post_to_review(self, post, ingested_at: str) -> Optional[RawReview]:
        try:
            published_at = datetime.fromtimestamp(post.created_utc, tz=timezone.utc).isoformat()
            author = str(post.author) if post.author else None
            text = f"{post.title}\n{post.selftext}".strip()
            return RawReview(
                id=make_stable_id("reddit", author, published_at, text),
                source_platform="reddit",
                raw_text=text,
                rating=None,
                author_id=author,
                published_at=published_at,
                source_url=f"https://www.reddit.com{post.permalink}",
                ingested_at=ingested_at,
                ingestion_batch_id=self._batch_id,
            )
        except Exception as exc:
            logger.debug("Failed to convert Reddit post %s: %s", getattr(post, "id", "?"), exc)
            return None

    def _comment_to_review(self, comment, post, ingested_at: str) -> Optional[RawReview]:
        try:
            published_at = datetime.fromtimestamp(comment.created_utc, tz=timezone.utc).isoformat()
            author = str(comment.author) if comment.author else None
            return RawReview(
                id=make_stable_id("reddit", author, published_at, comment.body),
                source_platform="reddit",
                raw_text=comment.body,
                rating=None,
                author_id=author,
                published_at=published_at,
                source_url=f"https://www.reddit.com{post.permalink}",
                ingested_at=ingested_at,
                ingestion_batch_id=self._batch_id,
            )
        except Exception as exc:
            logger.debug("Failed to convert Reddit comment %s: %s", getattr(comment, "id", "?"), exc)
            return None

    def _get_client(self):
        if self._reddit is not None:
            return self._reddit
        try:
            import praw
        except ImportError:
            raise ImportError("praw not installed: pip install praw")
        self._reddit = praw.Reddit(
            client_id=self._client_id,
            client_secret=self._client_secret,
            user_agent=self._user_agent,
            check_for_async=False,
        )
        return self._reddit
