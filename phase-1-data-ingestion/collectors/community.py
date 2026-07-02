import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

from collectors.base import CollectorInterface
from models.raw_review import RawReview, make_stable_id

logger = logging.getLogger(__name__)

COMMUNITY_BASE = "https://community.spotify.com"
# Board paths targeting music discovery and recommendation discussions
TARGET_BOARDS = [
    "/t5/Music/bd-p/Music",
    "/t5/Live-Music/bd-p/LiveMusic",
]
RATE_LIMIT_SECS = 3.0       # respectful scraping rate
REQUEST_TIMEOUT = 15
USER_AGENT = "spotify-review-collector/1.0 (research; non-commercial)"


class CommunityCollector(CollectorInterface):
    def __init__(self, batch_id: Optional[str] = None):
        self._batch_id = batch_id or str(uuid.uuid4())
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": USER_AGENT})
        self._robots = self._load_robots()

    def platform_name(self) -> str:
        return "community"

    def validate_credentials(self) -> bool:
        try:
            resp = self._session.get(COMMUNITY_BASE, timeout=REQUEST_TIMEOUT)
            return resp.status_code == 200
        except requests.RequestException as exc:
            logger.warning("Community connectivity check failed: %s", exc)
            return False

    def fetch(
        self,
        query: str = "",
        limit: int = 500,
        since_date: Optional[datetime] = None,
    ) -> list[RawReview]:
        ingested_at = datetime.now(timezone.utc).isoformat()
        reviews: list[RawReview] = []

        for board_path in TARGET_BOARDS:
            if len(reviews) >= limit:
                break
            board_url = COMMUNITY_BASE + board_path
            if not self._robots_allows(board_url):
                logger.warning("robots.txt disallows scraping: %s", board_url)
                continue
            batch = self._scrape_board(board_url, limit - len(reviews), ingested_at, since_date)
            reviews.extend(batch)

        return reviews[:limit]

    def _scrape_board(
        self,
        board_url: str,
        limit: int,
        ingested_at: str,
        since_date: Optional[datetime],
    ) -> list[RawReview]:
        reviews: list[RawReview] = []
        next_url: Optional[str] = board_url

        while next_url and len(reviews) < limit:
            soup = self._get_soup(next_url)
            if soup is None:
                break

            for post_url in self._extract_post_links(soup):
                if len(reviews) >= limit:
                    break
                if not self._robots_allows(post_url):
                    continue
                time.sleep(RATE_LIMIT_SECS)
                post_reviews = self._scrape_post(post_url, ingested_at, since_date)
                reviews.extend(post_reviews)

            next_url = self._extract_next_page(soup)
            time.sleep(RATE_LIMIT_SECS)

        return reviews

    def _scrape_post(
        self,
        post_url: str,
        ingested_at: str,
        since_date: Optional[datetime],
    ) -> list[RawReview]:
        soup = self._get_soup(post_url)
        if soup is None:
            return []

        reviews: list[RawReview] = []

        for article in soup.select("article.lia-component-message-view-widget-message-content, .lia-message-body"):
            body_el = article.select_one(".lia-message-body-content")
            if body_el is None:
                body_el = article
            text = body_el.get_text(separator=" ", strip=True)
            if not text:
                continue

            # Extract timestamp and author from surrounding context
            time_tag = article.find("time") or soup.find("time")
            published_at = time_tag.get("datetime", "") if time_tag else ""

            if since_date and published_at:
                try:
                    pub = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                    aware_since = since_date if since_date.tzinfo else since_date.replace(tzinfo=timezone.utc)
                    if pub < aware_since:
                        continue
                except ValueError:
                    pass

            author_el = article.select_one(".lia-user-name-link, .UserName, [data-author-login]")
            author = author_el.get_text(strip=True) if author_el else None

            reviews.append(RawReview(
                id=make_stable_id("community", author, published_at, text),
                source_platform="community",
                raw_text=text,
                rating=None,
                author_id=author,
                published_at=published_at,
                source_url=post_url,
                ingested_at=ingested_at,
                ingestion_batch_id=self._batch_id,
            ))

        return reviews

    def _get_soup(self, url: str) -> Optional[BeautifulSoup]:
        for attempt in range(3):
            try:
                resp = self._session.get(url, timeout=REQUEST_TIMEOUT)
                resp.raise_for_status()
                return BeautifulSoup(resp.text, "html.parser")
            except requests.RequestException as exc:
                logger.warning("Community GET failed (attempt %d) for %s: %s", attempt + 1, url, exc)
                if attempt < 2:
                    time.sleep(30)
        return None

    def _extract_post_links(self, soup: BeautifulSoup) -> list[str]:
        links: list[str] = []
        for a in soup.select("a.page-link, .lia-link-navigation .message-subject, h2 a"):
            href = a.get("href", "")
            if href and "/t5/" in href and "/m-p/" not in href:
                full = urljoin(COMMUNITY_BASE, href)
                if full not in links:
                    links.append(full)
        return links

    def _extract_next_page(self, soup: BeautifulSoup) -> Optional[str]:
        next_el = soup.select_one("a[rel='next'], .lia-paging-page-next")
        if next_el and next_el.get("href"):
            return urljoin(COMMUNITY_BASE, next_el["href"])
        return None

    def _load_robots(self) -> RobotFileParser:
        rp = RobotFileParser()
        try:
            rp.set_url(COMMUNITY_BASE + "/robots.txt")
            rp.read()
        except Exception as exc:
            logger.warning("Could not load community robots.txt: %s", exc)
        return rp

    def _robots_allows(self, url: str) -> bool:
        try:
            return self._robots.can_fetch(USER_AGENT, url)
        except Exception:
            return True  # allow if robots check itself errors
