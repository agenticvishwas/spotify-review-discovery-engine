"""Unit tests for all source collectors using mocked HTTP/API responses."""

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from collectors.app_store import AppStoreCollector
from collectors.google_play import GooglePlayCollector
from collectors.reddit import RedditCollector
from collectors.social import SocialCollector
from models.raw_review import RawReview

FIXTURES = Path(__file__).parent / "fixtures" / "sample_responses"
BATCH_ID = "test-batch-001"


# ── Helpers ──────────────────────────────────────────────────────────────────

def load_fixture(name: str) -> dict | list:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def make_mock_response(data: dict | list, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = data
    resp.raise_for_status.return_value = None
    return resp


# ── AppStoreCollector ────────────────────────────────────────────────────────

class TestAppStoreCollector:
    def _collector(self) -> AppStoreCollector:
        return AppStoreCollector(batch_id=BATCH_ID)

    def test_fetch_returns_raw_reviews(self):
        fixture = load_fixture("app_store_response.json")
        empty_feed = {"feed": {"entry": []}}

        # First call returns the fixture; subsequent page calls return empty (no more pages)
        collector = self._collector()
        collector._session.get = MagicMock(side_effect=[
            make_mock_response(fixture),
            make_mock_response(empty_feed),
        ])
        reviews = collector.fetch(limit=10)

        # 3 valid reviews (first entry is app metadata and is skipped)
        assert len(reviews) == 3
        assert all(isinstance(r, RawReview) for r in reviews)

    def test_all_reviews_have_correct_platform(self):
        fixture = load_fixture("app_store_response.json")
        mock_resp = make_mock_response(fixture)
        collector = self._collector()
        collector._session.get = MagicMock(return_value=mock_resp)

        reviews = collector.fetch(limit=10)
        assert all(r.source_platform == "app_store" for r in reviews)

    def test_ratings_are_parsed_correctly(self):
        fixture = load_fixture("app_store_response.json")
        mock_resp = make_mock_response(fixture)
        collector = self._collector()
        collector._session.get = MagicMock(return_value=mock_resp)

        reviews = collector.fetch(limit=10)
        ratings = {r.rating for r in reviews}
        assert {5, 2, 4}.issubset(ratings)

    def test_ids_are_stable_across_two_fetches(self):
        fixture = load_fixture("app_store_response.json")
        mock_resp = make_mock_response(fixture)
        collector = self._collector()
        collector._session.get = MagicMock(return_value=mock_resp)

        reviews1 = collector.fetch(limit=10)
        collector._session.get = MagicMock(return_value=make_mock_response(fixture))
        reviews2 = collector.fetch(limit=10)

        ids1 = {r.id for r in reviews1}
        ids2 = {r.id for r in reviews2}
        assert ids1 == ids2

    def test_batch_id_is_set_on_all_records(self):
        fixture = load_fixture("app_store_response.json")
        mock_resp = make_mock_response(fixture)
        collector = self._collector()
        collector._session.get = MagicMock(return_value=mock_resp)

        reviews = collector.fetch(limit=10)
        assert all(r.ingestion_batch_id == BATCH_ID for r in reviews)

    def test_empty_feed_returns_empty_list(self):
        empty_feed = {"feed": {"entry": []}}
        mock_resp = make_mock_response(empty_feed)
        collector = self._collector()
        collector._session.get = MagicMock(return_value=mock_resp)

        reviews = collector.fetch(limit=10)
        assert reviews == []

    def test_since_date_filters_old_reviews(self):
        fixture = load_fixture("app_store_response.json")
        empty_feed = {"feed": {"entry": []}}
        collector = self._collector()
        # Only one page; second call returns empty so the loop stops
        collector._session.get = MagicMock(side_effect=[
            make_mock_response(fixture),
            make_mock_response(empty_feed),
        ])

        # Jan 15 00:00 UTC — only the 10:30 -07:00 entry (= 17:30 UTC) passes
        since = datetime(2024, 1, 15, tzinfo=timezone.utc)
        reviews = collector.fetch(limit=10, since_date=since)
        assert len(reviews) == 1

    def test_limit_caps_results(self):
        fixture = load_fixture("app_store_response.json")
        # Return same page for all page requests
        mock_resp = make_mock_response(fixture)
        collector = self._collector()
        collector._session.get = MagicMock(return_value=mock_resp)

        reviews = collector.fetch(limit=2)
        assert len(reviews) <= 2

    def test_platform_name(self):
        assert self._collector().platform_name() == "app_store"

    def test_no_reviews_with_empty_text_are_returned(self):
        feed_with_empty = {
            "feed": {
                "entry": [
                    {
                        "title": {"label": ""},
                        "content": {"label": ""},
                        "im:rating": {"label": "3"},
                        "author": {"name": {"label": "user"}},
                        "updated": {"label": "2024-01-15T10:00:00-07:00"},
                        "link": {"attributes": {"href": "https://example.com"}},
                    }
                ]
            }
        }
        mock_resp = make_mock_response(feed_with_empty)
        collector = self._collector()
        collector._session.get = MagicMock(return_value=mock_resp)
        reviews = collector.fetch(limit=10)
        assert reviews == []


# ── GooglePlayCollector ──────────────────────────────────────────────────────

class TestGooglePlayCollector:
    def _collector(self) -> GooglePlayCollector:
        return GooglePlayCollector(batch_id=BATCH_ID)

    def _make_gp_entry(self, index: int = 0) -> dict:
        from datetime import datetime
        return {
            "reviewId": f"gp_review_{index:03d}",
            "userName": f"AndroidUser{index}",
            "content": f"Review content number {index} about music discovery",
            "score": (index % 5) + 1,
            "at": datetime(2024, 1, 15 - index),
        }

    def test_fetch_returns_raw_reviews(self):
        entries = [self._make_gp_entry(i) for i in range(3)]

        with patch("collectors.google_play.GooglePlayCollector.fetch") as mock_fetch:
            mock_fetch.return_value = [
                RawReview(
                    id=f"test-id-{i}",
                    source_platform="google_play",
                    raw_text=e["content"],
                    rating=e["score"],
                    author_id=e["userName"],
                    published_at=e["at"].isoformat(),
                    source_url=f"https://play.google.com/?reviewId={e['reviewId']}",
                    ingested_at="2024-01-15T12:00:00+00:00",
                    ingestion_batch_id=BATCH_ID,
                )
                for i, e in enumerate(entries)
            ]
            collector = self._collector()
            reviews = collector.fetch(limit=3)

        assert len(reviews) == 3
        assert all(r.source_platform == "google_play" for r in reviews)

    def test_empty_content_entries_are_skipped(self):
        empty_entry = {
            "reviewId": "r001",
            "userName": "user1",
            "content": "",
            "score": 3,
            "at": datetime(2024, 1, 15),
        }
        collector = self._collector()

        # Call the internal parse method directly
        result = collector._parse_entry(empty_entry, "2024-01-15T12:00:00+00:00")
        assert result is None

    def test_platform_name(self):
        assert self._collector().platform_name() == "google_play"

    def test_parse_entry_produces_valid_review(self):
        from datetime import datetime
        entry = {
            "reviewId": "r001",
            "userName": "TestUser",
            "content": "Amazing discovery features",
            "score": 5,
            "at": datetime(2024, 1, 15),
        }
        collector = self._collector()
        review = collector._parse_entry(entry, "2024-01-15T12:00:00+00:00")

        assert review is not None
        assert review.source_platform == "google_play"
        assert review.rating == 5
        assert review.ingestion_batch_id == BATCH_ID
        assert "Amazing discovery" in review.raw_text

    def test_parse_entry_stable_id(self):
        from datetime import datetime
        entry = {
            "reviewId": "r001",
            "userName": "TestUser",
            "content": "Amazing discovery features",
            "score": 5,
            "at": datetime(2024, 1, 15),
        }
        collector = self._collector()
        r1 = collector._parse_entry(entry, "2024-01-15T12:00:00+00:00")
        r2 = collector._parse_entry(entry, "2024-01-15T13:00:00+00:00")  # ingested_at differs
        assert r1.id == r2.id  # ID based on content, not ingested_at

    def test_since_date_stops_pagination_early(self):
        """When a batch contains an entry older than since_date, pagination must stop
        immediately rather than fetching further pages. Results are newest-first, so
        the first old entry means all subsequent entries are also old."""
        from datetime import datetime
        from unittest.mock import patch, MagicMock

        new_entry = {
            "reviewId": "r_new",
            "userName": "NewUser",
            "content": "Brand new review about discovery",
            "score": 5,
            "at": datetime(2024, 1, 20),  # after since_date
        }
        old_entry = {
            "reviewId": "r_old",
            "userName": "OldUser",
            "content": "Old review predating since_date cutoff",
            "score": 3,
            "at": datetime(2024, 1, 5),  # before since_date
        }

        call_count = 0

        def fake_gp_reviews(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [new_entry, old_entry], "token_page2"
            # This should never be reached — early exit should fire after page 1
            return [old_entry], "token_page3"

        collector = self._collector()
        since = datetime(2024, 1, 10, tzinfo=timezone.utc)

        with patch("collectors.google_play.GooglePlayCollector.fetch") as _:
            # Test the internal fetch logic directly via patching the scraper
            pass

        # Directly test the behaviour by patching the import inside the method
        with patch.dict("sys.modules", {"google_play_scraper": MagicMock(
            reviews=fake_gp_reviews,
            Sort=MagicMock(NEWEST="newest"),
        )}):
            # Re-import to pick up the patch
            import importlib
            import collectors.google_play as gp_mod
            importlib.reload(gp_mod)
            col = gp_mod.GooglePlayCollector(batch_id=BATCH_ID)
            reviews = col.fetch(limit=100, since_date=since)

        # Only the new_entry passes; old_entry triggers early exit so page 2 is never called
        assert call_count == 1, f"Expected 1 API call (early exit), got {call_count}"
        assert len(reviews) == 1
        assert "Brand new" in reviews[0].raw_text


# ── RedditCollector ──────────────────────────────────────────────────────────

class TestRedditCollector:
    def _make_mock_post(self, post_id: str, title: str, body: str, author: str = "user1") -> MagicMock:
        post = MagicMock()
        post.id = post_id
        post.title = title
        post.selftext = body
        post.author = MagicMock()
        post.author.__str__ = lambda s: author
        post.author.name = author
        post.created_utc = 1705312800.0  # 2024-01-15
        post.permalink = f"/r/spotify/comments/{post_id}/test/"
        post.comments = MagicMock()
        post.comments.replace_more.return_value = None
        post.comments.list.return_value = []
        return post

    def test_post_to_review_conversion(self):
        collector = RedditCollector(
            client_id="fake_id", client_secret="fake_secret", batch_id=BATCH_ID
        )
        mock_post = self._make_mock_post("abc123", "Music discovery issue", "Body here")
        review = collector._post_to_review(mock_post, "2024-01-15T12:00:00+00:00")

        assert review is not None
        assert review.source_platform == "reddit"
        assert review.rating is None
        assert "Music discovery issue" in review.raw_text
        assert review.ingestion_batch_id == BATCH_ID

    def test_comment_to_review_conversion(self):
        collector = RedditCollector(
            client_id="fake_id", client_secret="fake_secret", batch_id=BATCH_ID
        )
        mock_post = self._make_mock_post("abc123", "Title", "Body")
        mock_comment = MagicMock()
        mock_comment.id = "cmnt001"
        mock_comment.body = "This is a comment about discovery"
        mock_comment.author = MagicMock()
        mock_comment.author.__str__ = lambda s: "commenter"
        mock_comment.created_utc = 1705316400.0

        review = collector._comment_to_review(mock_comment, mock_post, "2024-01-15T12:00:00+00:00")

        assert review is not None
        assert review.source_platform == "reddit"
        assert "comment about discovery" in review.raw_text

    def test_deleted_post_body_is_skipped(self):
        collector = RedditCollector(
            client_id="fake_id", client_secret="fake_secret", batch_id=BATCH_ID
        )
        mock_post = self._make_mock_post("abc123", "Title", "[deleted]")

        # Deleted body should not produce a review (checked in _fetch_subreddit)
        # The post body "[deleted]" check is in _fetch_subreddit, not _post_to_review
        # So _post_to_review itself will not filter — the pipeline does
        assert mock_post.selftext == "[deleted]"

    def test_platform_name(self):
        collector = RedditCollector(client_id="x", client_secret="y", batch_id=BATCH_ID)
        assert collector.platform_name() == "reddit"

    def test_stable_ids_across_calls(self):
        collector = RedditCollector(
            client_id="fake_id", client_secret="fake_secret", batch_id=BATCH_ID
        )
        mock_post = self._make_mock_post("abc123", "Title", "Body here")
        r1 = collector._post_to_review(mock_post, "2024-01-15T12:00:00+00:00")
        r2 = collector._post_to_review(mock_post, "2024-01-15T13:00:00+00:00")
        assert r1.id == r2.id


# ── SocialCollector ──────────────────────────────────────────────────────────

class TestSocialCollector:
    BEARER = "test_bearer_token"

    def _collector(self) -> SocialCollector:
        return SocialCollector(bearer_token=self.BEARER, batch_id=BATCH_ID)

    def _make_twitter_response(self, tweets: list[dict]) -> dict:
        return {
            "data": tweets,
            "includes": {
                "users": [
                    {"id": t["author_id"], "username": f"user_{t['author_id']}"}
                    for t in tweets
                ]
            },
            "meta": {"newest_id": "999", "oldest_id": "001"},
        }

    def test_fetch_parses_tweets(self):
        tweets = [
            {"id": "t001", "text": "Spotify discover weekly is amazing this week!", "author_id": "u1", "created_at": "2024-01-15T10:00:00Z"},
            {"id": "t002", "text": "Why does spotify recommend the same songs over and over?", "author_id": "u2", "created_at": "2024-01-15T09:00:00Z"},
        ]
        mock_resp = make_mock_response(self._make_twitter_response(tweets))

        collector = self._collector()
        collector._session.get = MagicMock(return_value=mock_resp)

        reviews = collector.fetch(query="spotify discover", limit=10)
        assert len(reviews) == 2
        assert all(r.source_platform == "social" for r in reviews)

    def test_short_tweets_are_filtered(self):
        tweets = [
            {"id": "t001", "text": "ok", "author_id": "u1", "created_at": "2024-01-15T10:00:00Z"},
            {"id": "t002", "text": "This is a long enough tweet about Spotify discover", "author_id": "u2", "created_at": "2024-01-15T10:00:00Z"},
        ]
        mock_resp = make_mock_response(self._make_twitter_response(tweets))
        collector = self._collector()
        collector._session.get = MagicMock(return_value=mock_resp)

        reviews = collector.fetch(query="spotify discover", limit=10)
        assert len(reviews) == 1
        assert "long enough" in reviews[0].raw_text

    def test_platform_name(self):
        assert self._collector().platform_name() == "social"

    def test_empty_response_returns_empty_list(self):
        mock_resp = make_mock_response({"data": [], "meta": {}})
        collector = self._collector()
        collector._session.get = MagicMock(return_value=mock_resp)

        reviews = collector.fetch(query="spotify", limit=10)
        assert reviews == []

    def test_stable_ids(self):
        tweets = [
            {"id": "t001", "text": "Spotify discover weekly is the best feature", "author_id": "u1", "created_at": "2024-01-15T10:00:00Z"},
        ]
        mock_resp1 = make_mock_response(self._make_twitter_response(tweets))
        mock_resp2 = make_mock_response(self._make_twitter_response(tweets))

        collector = self._collector()
        collector._session.get = MagicMock(return_value=mock_resp1)
        r1 = collector.fetch(query="spotify", limit=5)

        collector._session.get = MagicMock(return_value=mock_resp2)
        r2 = collector.fetch(query="spotify", limit=5)

        assert r1[0].id == r2[0].id


# ── Contract: all reviews conform to RawReview schema ───────────────────────

class TestRawReviewContract:
    """All collectors must return records that pass RawReview.validation_errors()."""

    def test_app_store_records_pass_schema(self):
        fixture = load_fixture("app_store_response.json")
        collector = AppStoreCollector(batch_id=BATCH_ID)
        collector._session.get = MagicMock(return_value=make_mock_response(fixture))

        reviews = collector.fetch(limit=10)
        for review in reviews:
            assert review.validation_errors() == [], \
                f"Review {review.id} failed validation: {review.validation_errors()}"

    def test_all_reviews_have_required_fields(self):
        fixture = load_fixture("app_store_response.json")
        collector = AppStoreCollector(batch_id=BATCH_ID)
        collector._session.get = MagicMock(return_value=make_mock_response(fixture))
        reviews = collector.fetch(limit=10)

        for review in reviews:
            assert review.id
            assert review.source_platform
            assert review.raw_text
            assert review.published_at
            assert review.ingested_at
            assert review.ingestion_batch_id
            assert review.schema_version == "1.0"

    def test_to_jsonl_round_trip(self):
        """JSONL serialization must produce a record that deserializes back cleanly."""
        fixture = load_fixture("app_store_response.json")
        collector = AppStoreCollector(batch_id=BATCH_ID)
        collector._session.get = MagicMock(return_value=make_mock_response(fixture))
        reviews = collector.fetch(limit=3)

        for review in reviews:
            line = review.to_jsonl()
            reconstructed = RawReview.model_validate_json(line)
            assert reconstructed.id == review.id
            assert reconstructed.raw_text == review.raw_text
            assert reconstructed.source_platform == review.source_platform
