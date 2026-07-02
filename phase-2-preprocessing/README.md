# Phase 2 — Preprocessing

## Objective

Transform raw, noisy, heterogeneous reviews into clean, normalized, deduplicated records ready for AI analysis.

This phase has no AI. Every transformation is deterministic and rule-based.

---

## Responsibilities

- Strip HTML, emoji, and non-linguistic noise
- Detect and filter non-English reviews
- Remove duplicates (exact and near-duplicate)
- Normalize ratings to a consistent 1–5 scale
- Score review quality (substantiveness)
- Produce NormalizedReview records with full lineage to source

---

## Non-Responsibilities

- Interpreting meaning or intent (Phase 3)
- Clustering (Phase 4)
- Generating insights (Phase 5)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│             INPUT: RawReview[] from Phase 1                     │
│             (JSONL files from raw_reviews/ directory)           │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                   CLEANING STAGE                                │
│                                                                 │
│  HTMLCleaner       → strip tags, decode entities               │
│  EmojiHandler      → replace or remove emoji characters        │
│  WhitespaceCleaner → collapse excess whitespace                 │
│  SpecialCharFilter → remove non-printable characters            │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                   LANGUAGE DETECTION STAGE                      │
│                                                                 │
│  LanguageDetector → detect language code                        │
│  EnglishFilter    → pass English, flag others                   │
│                   → Non-English: mark as filtered, preserve ID  │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                   DEDUPLICATION STAGE                           │
│                                                                 │
│  ExactDeduplicator  → SHA-256 hash of clean_text                │
│  NearDupDetector    → MinHash / Jaccard similarity > 0.85       │
│                     → Mark duplicates, preserve one canonical   │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                   NORMALIZATION STAGE                           │
│                                                                 │
│  RatingNormalizer  → map all platforms to 1.0–5.0 float         │
│  DateNormalizer    → ISO8601 with timezone normalization         │
│  PlatformMapper    → canonical platform enum                    │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                   QUALITY SCORING STAGE                         │
│                                                                 │
│  QualityScorer     → score 0.0–1.0 based on:                   │
│                       - word count (min 10)                     │
│                       - sentence count                          │
│                       - presence of specific content            │
│                       - not just rating with no text            │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│             OUTPUT: NormalizedReview[] (JSONL)                  │
│             + preprocessing_quality_report.json                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Model

### NormalizedReview Schema

```json
{
  "id": "uuid-v4",
  "source_review_id": "uuid — links to RawReview.id",
  "clean_text": "cleaned and normalized text",
  "normalized_rating": "1.0–5.0 float or null",
  "language": "ISO 639-1 code (e.g. 'en')",
  "word_count": "integer",
  "sentence_count": "integer",
  "quality_score": "0.0–1.0",
  "is_duplicate": "boolean",
  "duplicate_of_id": "uuid or null",
  "platform": "app_store | google_play | reddit | community | social",
  "published_at": "ISO8601 normalized",
  "normalized_at": "ISO8601",
  "schema_version": "1.0",
  "filters_applied": ["html_strip", "emoji_remove", "language_filter"]
}
```

### PreprocessingBatch Schema

```json
{
  "batch_id": "uuid",
  "source_batch_ids": ["uuid"],
  "started_at": "ISO8601",
  "completed_at": "ISO8601",
  "total_input": "integer",
  "total_output": "integer",
  "filtered_non_english": "integer",
  "filtered_duplicates": "integer",
  "filtered_low_quality": "integer"
}
```

---

## Component Specifications

### HTMLCleaner

- Strip all HTML tags using `beautifulsoup4`
- Decode HTML entities (`&amp;` → `&`, `&lt;` → `<`)
- Preserve paragraph structure by replacing block tags with newlines

### EmojiHandler

- Mode: `remove` (default) — strip all emoji characters
- Alternative mode: `replace` — substitute with text description via `emoji` library
- Configuration-driven (allows switching without code changes)

### LanguageDetector

- Library: `langdetect` or `langid`
- Minimum text length for reliable detection: 20 characters
- Confidence threshold: 0.90
- Reviews below threshold: marked as `language: "unknown"`, excluded from pipeline

### ExactDeduplicator

- Hash: SHA-256 of `clean_text.strip().lower()`
- Store seen hashes in-memory during a batch run
- Cross-batch deduplication: check against persisted hash index

### NearDupDetector

- Algorithm: MinHash with Jaccard similarity
- Threshold: 0.85 (reviews ≥ 85% similar are duplicates)
- Canonical record: earliest `published_at` wins
- Library: `datasketch`

### RatingNormalizer

| Platform | Source Format | Normalized |
|---|---|---|
| App Store | 1–5 integer | 1.0–5.0 float |
| Google Play | 1–5 integer | 1.0–5.0 float |
| Reddit | upvote score | null (no star rating) |
| Community | none / custom | null |
| Social | none | null |

### QualityScorer

Scoring function (deterministic):

```
score = 0.0
if word_count >= 10: score += 0.3
if word_count >= 30: score += 0.2
if sentence_count >= 2: score += 0.2
if contains_specific_content: score += 0.2
if not_generic_template: score += 0.1
```

Threshold: reviews with `quality_score < 0.3` are excluded from AI analysis (but still stored).

---

## Directory Structure

```
phase-2-preprocessing/
├── README.md                       ← This file
├── cleaners/
│   ├── __init__.py
│   ├── html_cleaner.py
│   ├── emoji_handler.py
│   ├── whitespace_cleaner.py
│   └── special_char_filter.py
├── normalizers/
│   ├── __init__.py
│   ├── rating_normalizer.py
│   ├── date_normalizer.py
│   └── platform_mapper.py
├── deduplication/
│   ├── __init__.py
│   ├── exact_deduplicator.py
│   └── near_dup_detector.py
├── validators/
│   ├── __init__.py
│   ├── language_detector.py
│   └── quality_scorer.py
├── tests/
│   ├── test_cleaners.py
│   ├── test_normalizers.py
│   ├── test_deduplication.py
│   └── test_quality_scorer.py
├── preprocessing_pipeline.py       ← Orchestrates all stages
└── quality_report.py               ← Generates preprocessing summary
```

---

## Pipeline Flow

```
1. Load RawReview JSONL files from Phase 1 output
2. For each record:
   a. HTMLCleaner → remove markup
   b. EmojiHandler → handle emoji
   c. WhitespaceCleaner → normalize whitespace
   d. SpecialCharFilter → remove non-printable chars
   e. LanguageDetector → detect language
   f. EnglishFilter → exclude non-English
   g. ExactDeduplicator → check SHA-256 hash
   h. NearDupDetector → check MinHash similarity
   i. RatingNormalizer → normalize rating
   j. DateNormalizer → normalize timestamp
   k. QualityScorer → score review quality
   l. Write NormalizedReview to output JSONL
3. Write PreprocessingBatch summary
4. Emit preprocessing_quality_report.json
```

---

## Quality Report Output

```json
{
  "batch_id": "uuid",
  "run_date": "ISO8601",
  "total_input": 2489,
  "total_output": 1847,
  "stages": {
    "html_cleaning": {"modified": 312},
    "language_filter": {"excluded": 203, "language_breakdown": {"es": 89, "pt": 67}},
    "exact_dedup": {"removed": 145},
    "near_dup": {"removed": 78},
    "quality_filter": {"excluded": 216, "avg_quality_score": 0.61}
  },
  "output_quality": {
    "avg_word_count": 47,
    "avg_quality_score": 0.74,
    "rating_coverage": 0.62
  }
}
```

---

## Testing Strategy

| Test Type | Coverage |
|---|---|
| Unit | Each cleaner with known input/output pairs |
| Unit | Language detection accuracy on labeled samples |
| Unit | Deduplication detects exact and near-duplicates |
| Unit | Quality scorer produces expected scores |
| Integration | Full pipeline from JSONL input to JSONL output |
| Regression | Previously-seen edge cases (HTML with scripts, all-emoji reviews) |

---

## Success Criteria

- No clean_text field contains raw HTML tags after cleaning
- All duplicates are flagged (not silently removed)
- Lineage to source_review_id is preserved on every record
- Quality score is present on every output record
- Pipeline is deterministic: same input always produces same output

---

## Dependencies

- `beautifulsoup4` — HTML cleaning
- `langdetect` — Language detection
- `datasketch` — MinHash deduplication
- `emoji` — Emoji handling
- `pydantic` — Schema validation
- `hashlib` — SHA-256 hashing (stdlib)

---

## Phase 2 → Phase 3 Contract

Phase 2 writes JSONL files conforming to NormalizedReview schema.
Phase 3 reads only records where `is_duplicate = false` and `quality_score >= 0.3`.
