# Phase 3 — AI Analysis (Per-Review)

## Objective

Use an LLM to extract structured semantic metadata from each normalized review.

This phase is the primary AI layer of the system. It transforms human language into structured signals that all downstream phases can reason about quantitatively.

---

## Responsibilities

- Send each normalized review to an LLM with a structured extraction prompt
- Extract sentiment, intent, friction signals, JTBD signals, root causes, feature mentions, user segment signals
- Return structured JSON conforming to AnalyzedReview schema
- Attach confidence scores to all AI outputs
- Version and evaluate prompts
- Handle rate limits, failures, and retries gracefully

---

## Non-Responsibilities

- Clustering or grouping reviews (Phase 4)
- Generating high-level insights (Phase 5)
- Storing results persistently (Phase 6)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│         INPUT: NormalizedReview[] from Phase 2                  │
│         Filter: is_duplicate=false, quality_score >= 0.3        │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                   PROMPT BUILDER                                │
│                                                                 │
│  PromptTemplate v1.2 + NormalizedReview → Formatted Prompt      │
│  Includes: system role, task definition, output schema          │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                   LLM CLIENT                                    │
│                                                                 │
│  AnthropicClient                                                │
│  → claude-sonnet-4-6 (default)                                  │
│  → Structured output via tool_use / JSON mode                   │
│  → Temperature: 0.1 (near-deterministic)                        │
│  → Max tokens: 1024                                             │
│  → Retry logic: exponential backoff, max 3 retries              │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                   RESPONSE VALIDATOR                            │
│                                                                 │
│  JSON schema validation → reject malformed responses            │
│  Confidence estimator  → score based on response certainty      │
│  Hallucination guard   → verify feature_mentions exist in text  │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                   BATCH PROCESSOR                               │
│                                                                 │
│  Concurrency: 5 parallel requests (rate limit safe)             │
│  Progress tracking: processed / total                           │
│  Resume capability: skip already-analyzed review IDs            │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│         OUTPUT: AnalyzedReview[] (JSONL)                        │
│         + analysis_quality_report.json                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Model

### AnalyzedReview Schema

```json
{
  "id": "uuid-v4",
  "normalized_review_id": "uuid — links to NormalizedReview.id",
  "source_review_id": "uuid — propagated lineage to RawReview.id",
  "sentiment": "positive | negative | neutral | mixed",
  "sentiment_score": "-1.0 to 1.0",
  "discovery_friction_detected": "boolean",
  "discovery_friction_description": "string | null",
  "primary_complaint": "string | null",
  "primary_praise": "string | null",
  "feature_mentions": ["string"],
  "jtbd_signal": "string describing what user is trying to accomplish | null",
  "user_intent": "string | null",
  "root_cause_signal": "string | null",
  "user_segment_signal": "power_user | casual | new | churned | unknown",
  "emotion_tags": ["frustration | delight | confusion | boredom | hope"],
  "listening_behavior_signal": "repetitive | exploratory | mood-based | unknown",
  "confidence_score": "0.0–1.0",
  "analysis_model": "claude-sonnet-4-6",
  "prompt_version": "1.2",
  "analyzed_at": "ISO8601",
  "schema_version": "1.0",
  "analysis_tokens_used": "integer"
}
```

---

## Prompt Specification

### Review Analysis Prompt v1.2

**Purpose:** Extract structured discovery-related signals from a single Spotify user review.

**Version:** 1.2
**Model:** claude-sonnet-4-6
**Temperature:** 0.1
**Max Tokens:** 1024

**System Role:**
```
You are a product research analyst specializing in music streaming products.
Your task is to extract structured insights from Spotify user reviews to support product discovery research.
You must be precise, evidence-grounded, and never invent information not present in the review text.
When uncertain, express low confidence rather than guessing.
Always return valid JSON matching the specified schema.
```

**Extraction Schema (Tool Definition):**
```json
{
  "name": "extract_review_signals",
  "description": "Extract structured product signals from a Spotify user review",
  "input_schema": {
    "type": "object",
    "properties": {
      "sentiment": {
        "type": "string",
        "enum": ["positive", "negative", "neutral", "mixed"],
        "description": "Overall sentiment of the review"
      },
      "sentiment_score": {
        "type": "number",
        "description": "Sentiment intensity from -1.0 (very negative) to 1.0 (very positive)"
      },
      "discovery_friction_detected": {
        "type": "boolean",
        "description": "True if the review mentions difficulty discovering new music or repetitive recommendations"
      },
      "discovery_friction_description": {
        "type": "string",
        "description": "Direct quote or paraphrase of the discovery friction described, null if none"
      },
      "primary_complaint": {
        "type": "string",
        "description": "The main complaint expressed, null if review is positive"
      },
      "primary_praise": {
        "type": "string",
        "description": "The main praise expressed, null if review is negative"
      },
      "feature_mentions": {
        "type": "array",
        "items": {"type": "string"},
        "description": "Specific Spotify features mentioned (e.g., Discover Weekly, Radio, Daily Mix)"
      },
      "jtbd_signal": {
        "type": "string",
        "description": "What job is the user trying to accomplish? (e.g., 'find new music that matches current mood')"
      },
      "user_intent": {
        "type": "string",
        "description": "What the user wants to achieve beyond the immediate complaint"
      },
      "root_cause_signal": {
        "type": "string",
        "description": "The underlying cause of the problem described, if inferable"
      },
      "user_segment_signal": {
        "type": "string",
        "enum": ["power_user", "casual", "new", "churned", "unknown"],
        "description": "Inferred user type based on vocabulary and usage patterns"
      },
      "emotion_tags": {
        "type": "array",
        "items": {"type": "string", "enum": ["frustration", "delight", "confusion", "boredom", "hope", "disappointment"]},
        "description": "Emotional signals detected in the review"
      },
      "listening_behavior_signal": {
        "type": "string",
        "enum": ["repetitive", "exploratory", "mood-based", "activity-based", "unknown"],
        "description": "What listening pattern does the user describe or imply?"
      },
      "confidence_score": {
        "type": "number",
        "description": "0.0–1.0 confidence in the accuracy of this extraction"
      }
    },
    "required": ["sentiment", "sentiment_score", "discovery_friction_detected", "confidence_score"]
  }
}
```

**User Message Template:**
```
Analyze the following Spotify user review and extract structured signals.

Platform: {platform}
Rating: {normalized_rating}/5 (null if unavailable)
Review Text:
---
{clean_text}
---

Focus especially on:
1. Any mention of difficulty discovering new music
2. Complaints about repetitive or stale recommendations
3. What the user is fundamentally trying to accomplish (their Job To Be Done)
4. The root cause of any problem they describe
5. Which specific Spotify features they reference

Return your analysis as a JSON object matching the schema provided.
```

---

## Prompt Engineering Rules

1. Prompts are versioned files in `prompts/` — never hardcoded in code.
2. Every prompt change requires updating the version string.
3. Every prompt change requires a re-evaluation run before production use.
4. Prompts are structured as: system role + task definition + output schema + examples.
5. Temperature is always ≤ 0.2 for extraction tasks.

---

## Evaluation Framework

### Evaluation Dataset

- 100 hand-labeled reviews per platform (500 total)
- Labels: sentiment, discovery_friction_detected, jtbd_signal (human-judged)
- Maintained in `evaluations/eval_dataset.jsonl`

### Evaluation Metrics

| Metric | Threshold |
|---|---|
| Sentiment accuracy | ≥ 85% |
| Discovery friction detection F1 | ≥ 0.80 |
| Feature mention precision | ≥ 90% |
| JSON schema compliance | 100% |
| Average confidence score | ≥ 0.70 |

### Regression Guard

Before any prompt version bump: run `evaluations/run_eval.py` and confirm all thresholds pass.

---

## Directory Structure

```
phase-3-ai-analysis/
├── README.md                       ← This file
├── prompts/
│   ├── review_analysis_v1.2.md     ← Current prompt (versioned)
│   ├── review_analysis_v1.1.md     ← Previous version (archived)
│   └── PROMPT_CHANGELOG.md         ← Change log with reasons
├── analyzers/
│   ├── __init__.py
│   ├── llm_client.py               ← Anthropic API wrapper with retry
│   ├── prompt_builder.py           ← Fills prompt template with review data
│   ├── response_validator.py       ← JSON schema validation + hallucination guard
│   └── batch_processor.py          ← Concurrency, progress, resume logic
├── schemas/
│   ├── analyzed_review.py          ← AnalyzedReview dataclass + Pydantic model
│   └── extraction_tool.json        ← JSON Schema for Claude tool_use call
├── evaluations/
│   ├── eval_dataset.jsonl          ← 500 hand-labeled reviews
│   ├── run_eval.py                 ← Evaluation runner
│   └── eval_reports/               ← Timestamped evaluation results
├── tests/
│   ├── test_prompt_builder.py
│   ├── test_response_validator.py
│   ├── test_batch_processor.py
│   └── fixtures/
│       └── sample_analyzed_reviews.jsonl
└── analysis_pipeline.py            ← Orchestrates batch analysis
```

---

## Pipeline Flow

```
1. Load NormalizedReview JSONL (filter: not duplicate, quality >= 0.3)
2. Load already-analyzed IDs from output (for resume capability)
3. For each unanalyzed review:
   a. PromptBuilder → format review into prompt
   b. LLMClient → call Claude API with tool_use
   c. ResponseValidator → validate JSON schema
   d. HallucinationGuard → check feature_mentions exist in source text
   e. Write AnalyzedReview to output JSONL
   f. Track token usage
4. Write analysis_quality_report.json
```

---

## Cost Management

- Estimated: ~200–400 tokens per review
- 10,000 reviews ≈ 2–4M tokens
- Use Claude Haiku for first-pass extraction (speed + cost)
- Use Claude Sonnet for re-analysis of low-confidence extractions
- Cache results: same review_id never analyzed twice

---

## Error Handling

| Error | Handling |
|---|---|
| API rate limit | Exponential backoff, max 5 retries |
| Invalid JSON response | Retry once with explicit JSON instruction |
| Schema validation failure | Log failure, write null extraction with error flag |
| Hallucination detected | Override field to null, reduce confidence_score |
| API timeout | Retry with 60s delay |

---

## Testing Strategy

| Test Type | Coverage |
|---|---|
| Unit | PromptBuilder produces expected formatted string |
| Unit | ResponseValidator rejects malformed responses |
| Unit | HallucinationGuard correctly identifies invented features |
| Eval | 500-review labeled dataset meets accuracy thresholds |
| Integration | End-to-end: NormalizedReview → AnalyzedReview |

---

## Success Criteria

- 100% of outputs conform to AnalyzedReview JSON schema
- Sentiment accuracy ≥ 85% on evaluation dataset
- Discovery friction F1 ≥ 0.80
- No unhandled API errors in production runs
- Prompt version is recorded on every output record

---

## Dependencies

- `anthropic` — Claude API SDK
- `pydantic` — Schema validation
- `asyncio` / `httpx` — Async batch processing
- `tenacity` — Retry logic

---

## Phase 3 → Phase 4 Contract

Phase 3 writes JSONL files conforming to AnalyzedReview schema.
Phase 4 reads those files to generate embeddings and perform clustering.
