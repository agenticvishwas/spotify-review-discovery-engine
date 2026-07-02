# Phase 1 — Data Ingestion

## Objective

Collect raw customer feedback from all public platforms into a local, immutable store.

This phase has no AI. Every decision is deterministic. The goal is completeness, reliability, and fidelity — not analysis.

---

## Responsibilities

- Connect to each source platform
- Fetch reviews with pagination and rate limiting
- Validate basic structural integrity of incoming records
- Assign stable unique identifiers
- Persist raw reviews without modification
- Emit ingestion quality reports

---

## Non-Responsibilities

- Cleaning or normalizing text (Phase 2)
- Analyzing meaning (Phase 3)
- Deduplicating (Phase 2)
- Enriching with metadata (Phase 3)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    SOURCE PLATFORMS                             │
│                                                                 │
│  App Store  Google Play  Reddit  Community  Social Media        │
└──────┬──────────┬───────────┬────────┬──────────┬──────────────┘
       │          │           │        │          │
       ▼          ▼           ▼        ▼          ▼
┌──────────────────────────────────────────────────────────────────┐
│                   COLLECTOR LAYER                                │
│                                                                  │
│  AppStoreCollector    GooglePlayCollector    RedditCollector      │
│  CommunityCollector   SocialCollector                            │
│                                                                  │
│  Each collector implements: CollectorInterface                   │
│  → fetch(query, limit, since_date) → RawReview[]                │
└──────────────────────────────┬───────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                   INGESTION PIPELINE                             │
│                                                                  │
│  1. Run each collector                                           │
│  2. Assign batch_id and review_id                                │
│  3. Validate required fields (text, platform, timestamp)         │
│  4. Reject malformed records → error_log                         │
│  5. Write valid records to raw storage                           │
└──────────────────────────────┬───────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                   RAW STORAGE                                    │
│                                                                  │
│  raw_reviews/                                                    │
│    {platform}/                                                   │
│      {YYYY-MM-DD}/                                               │
│        {batch_id}.jsonl                                          │
│                                                                  │
│  Immutable after write. Never modified by downstream phases.     │
└──────────────────────────────────────────────────────────────────┘
```

---

## Data Model

### RawReview Schema

```json
{
  "id": "uuid-v4",
  "source_platform": "app_store | google_play | reddit | community | social",
  "raw_text": "original unmodified text",
  "rating": "integer 1-5 or null",
  "author_id": "platform-specific identifier or null",
  "published_at": "ISO8601 timestamp",
  "source_url": "canonical URL to original review",
  "ingested_at": "ISO8601 timestamp",
  "ingestion_batch_id": "uuid-v4",
  "schema_version": "1.0"
}
```

### IngestionBatch Schema

```json
{
  "batch_id": "uuid-v4",
  "platform": "string",
  "started_at": "ISO8601",
  "completed_at": "ISO8601",
  "total_fetched": "integer",
  "total_valid": "integer",
  "total_rejected": "integer",
  "query_params": {}
}
```

---

## Component Specifications

### CollectorInterface

Every platform collector must implement this contract:

```python
class CollectorInterface(ABC):
    def fetch(
        self,
        query: str,
        limit: int,
        since_date: datetime
    ) -> list[RawReview]:
        ...

    def validate_credentials(self) -> bool:
        ...

    def platform_name(self) -> str:
        ...
```

### AppStoreCollector

- Source: Apple App Store RSS / iTunes Search API
- Target App ID: Spotify (id324684580)
- Pagination: offset-based, max 500 per request
- Rate limit: 1 request per second
- Fields captured: title, body, rating, author, date, version

### GooglePlayCollector

- Source: Google Play Store (via google-play-scraper)
- Package: com.spotify.music
- Pagination: token-based
- Rate limit: 2 seconds between requests
- Fields captured: content, score, thumbsUp, reviewCreatedVersion, at, userName

### RedditCollector

- Source: Reddit API (PRAW)
- Target subreddits: r/spotify, r/SpotifyTheftClaims, r/Music
- Search keywords: discovery, recommend, repetitive, "same songs", "Discover Weekly"
- Fetch: top posts + comments, sorted by relevance and recency
- Rate limit: Reddit API tier (60 req/min authenticated)

### CommunityCollector

- Source: Spotify Community Forums (web scraping)
- Target sections: Music → Music Recommendations, Features → Music Discovery
- Extract: post body, reply bodies, votes, date
- Rate limit: 1 request per 3 seconds (respectful scraping)
- Robots.txt compliance required

### SocialCollector

- Source: Twitter/X API v2 (optional — requires API key)
- Query: "spotify recommend" OR "spotify discovery" OR "discover weekly"
- Filter: English language, minimum 10 characters
- Rate limit: API tier constraints

---

## Directory Structure

```
phase-1-data-ingestion/
├── README.md                    ← This file
├── collectors/
│   ├── __init__.py
│   ├── base.py                  ← CollectorInterface ABC
│   ├── app_store.py             ← AppStoreCollector
│   ├── google_play.py           ← GooglePlayCollector
│   ├── reddit.py                ← RedditCollector
│   ├── community.py             ← CommunityCollector
│   └── social.py                ← SocialCollector
├── models/
│   ├── __init__.py
│   ├── raw_review.py            ← RawReview dataclass + validation
│   └── ingestion_batch.py       ← IngestionBatch dataclass
├── storage/
│   ├── __init__.py
│   └── raw_store.py             ← JSONL writer with path conventions
├── tests/
│   ├── test_collectors.py       ← Unit tests with mocked responses
│   ├── test_models.py           ← Schema validation tests
│   └── fixtures/
│       └── sample_responses/    ← Saved API response fixtures
├── ingestion_pipeline.py        ← Orchestrates all collectors
└── quality_report.py            ← Generates ingestion quality summary
```

---

## Ingestion Pipeline Flow

```
1. Load configuration (platforms, date range, limits)
2. For each configured platform:
   a. Instantiate collector
   b. Validate credentials
   c. Fetch reviews in batches
   d. For each review:
      - Generate stable UUID (hash of platform + author + date + text[:50])
      - Validate required fields
      - Reject if text is empty, missing platform, or missing date
      - Write valid record to JSONL
      - Log rejected record to error log
3. Write IngestionBatch summary
4. Emit quality_report.json
```

---

## Quality Report Output

```json
{
  "batch_id": "uuid",
  "run_date": "ISO8601",
  "platforms": {
    "app_store": {
      "fetched": 500,
      "valid": 498,
      "rejected": 2,
      "rejection_reasons": {"empty_text": 2}
    }
  },
  "total_fetched": 2500,
  "total_valid": 2489,
  "total_rejected": 11
}
```

---

## Error Handling

| Error | Handling |
|---|---|
| API rate limit exceeded | Exponential backoff, max 3 retries |
| Network timeout | Retry with 30s delay, log warning |
| Missing required field | Reject record, log to error file |
| Platform unavailable | Skip platform, emit warning in report |
| Auth failure | Halt collector, raise critical error |

---

## Testing Strategy

| Test Type | What to Test |
|---|---|
| Unit | Each collector with mocked HTTP responses |
| Schema | RawReview validation accepts/rejects correct inputs |
| Integration | End-to-end pipeline with a small fixture dataset |
| Contract | Output JSONL matches RawReview schema exactly |

---

## Success Criteria

- All configured platforms return reviews without crashing
- Zero reviews are silently dropped (all rejections logged)
- Raw storage is immutable (no downstream phase writes to it)
- Ingestion is idempotent (same run twice produces same IDs)
- Quality report is generated after every run

---

## Dependencies

- `google-play-scraper` — Google Play reviews
- `praw` — Reddit API client
- `requests` / `httpx` — HTTP calls
- `beautifulsoup4` — Community forum scraping
- `uuid` — Stable ID generation
- `pydantic` — Schema validation

---

## Phase 1 → Phase 2 Contract

Phase 1 writes JSONL files conforming to the RawReview schema.
Phase 2 reads those files. The contract is the schema.

Breaking this contract requires updating both phases and the master ARCHITECTURE.md.
