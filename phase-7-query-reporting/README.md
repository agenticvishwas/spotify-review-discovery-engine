# Phase 7 — Query & Reporting Interface

## Objective

Enable Product Managers to query the knowledge base in natural language and receive evidence-backed answers, dashboards, and structured reports in minutes rather than days.

This is the PM-facing layer — the only phase that produces human-readable outputs.

---

## Responsibilities

- Accept natural language questions from Product Managers
- Translate questions into structured database and vector queries
- Generate evidence-backed answers with source traceability
- Produce dashboards showing insight distributions and trends
- Generate structured report templates (opportunity list, JTBD map, segment profiles)
- Surface confidence levels and supporting evidence for every output

---

## Non-Responsibilities

- Running data pipelines (Phases 1–5)
- Writing to the database (Phase 6)
- Generating insights (Phase 5)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│         INPUT: Phase 6 Knowledge Base                           │
│         (Structured DB + Vector Store + Evidence Index)         │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                 ┌─────────────┴─────────────┐
                 │                           │
                 ▼                           ▼
┌────────────────────────┐   ┌───────────────────────────────────┐
│  NATURAL LANGUAGE      │   │  DASHBOARD LAYER                  │
│  QUERY ENGINE          │   │                                   │
│                        │   │  Streamlit Application            │
│  1. Parse PM question  │   │                                   │
│  2. Classify intent    │   │  Pages:                           │
│  3. Generate DB/vector │   │  - Overview                       │
│     query plan         │   │  - Discovery Insights             │
│  4. Execute queries    │   │  - JTBD Map                       │
│  5. Retrieve evidence  │   │  - Opportunity List               │
│  6. Synthesize answer  │   │  - Segment Explorer               │
│  7. Format with        │   │  - NL Query Interface             │
│     confidence + links │   │  - Evidence Viewer                │
└────────────────────────┘   └───────────────────────────────────┘
                 │                           │
                 └─────────────┬─────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                   REPORT GENERATOR                              │
│                                                                 │
│  ReportTemplates:                                               │
│  - Executive Summary (top 5 opportunities)                      │
│  - Opportunity List (ranked, with evidence)                     │
│  - JTBD Map (all jobs, satisfaction scores)                     │
│  - Segment Profiles (behavioral characterization)               │
│  - Discovery Friction Report (platform comparison)              │
│                                                                 │
│  Formats: Markdown | JSON | CSV                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Natural Language Query Engine

### Supported Query Intents

| Intent | Example Question | Query Strategy |
|---|---|---|
| Discovery friction | "Why do users struggle to discover new music?" | Filter analyzed_reviews WHERE discovery_friction_detected=true → aggregate |
| Feature problems | "What do users say about Discover Weekly?" | Filter by feature_mentions='Discover Weekly' → sentiment + themes |
| Segment problems | "What do power users complain about?" | Filter by user_segment_signal='power_user' → top complaints |
| JTBD lookup | "What jobs are users trying to accomplish?" | Retrieve all JTBDProfile records → summarize |
| Opportunity list | "Which opportunities have the highest potential?" | Sort insights by opportunity_score DESC → top 10 |
| Trend query | "What problems are getting worse over time?" | Filter clusters by trend_direction='increasing' |
| Evidence retrieval | "Show me reviews that mention repetitive music" | Vector search in reviews collection → return verbatims |

### Query Flow

```
1. User inputs natural language question
2. IntentClassifier → determine query intent category
3. QueryPlanner → generate query plan:
   - Which DB tables to query
   - Which vector collections to search
   - What filters to apply
4. QueryExecutor:
   a. Run SQL queries via InsightRepository
   b. Run semantic search via ChromaDB
   c. Merge results
5. EvidenceRetriever → attach supporting verbatims
6. AnswerSynthesizer:
   - Call Claude with: question + query results + evidence
   - Generate structured prose answer
   - Include confidence, evidence list, caveats
7. Return: answer + evidence + source_review_ids
```

### Answer Format

```json
{
  "question": "Why do users struggle to discover new music?",
  "answer": "prose explanation generated by Claude",
  "confidence": "high | medium | low",
  "key_findings": [
    {
      "finding": "concise finding statement",
      "evidence_count": 312,
      "supporting_reviews": ["uuid", "uuid"],
      "verbatims": ["direct quote 1", "direct quote 2"]
    }
  ],
  "related_insights": ["insight_id_1", "insight_id_2"],
  "generated_at": "ISO8601"
}
```

---

## Dashboard Design

### Page 1: Overview

Widgets:
- Total reviews analyzed (by platform)
- Discovery friction rate (% of all reviews)
- Top 3 opportunities (opportunity_score)
- Sentiment distribution by platform
- Review volume over time

### Page 2: Discovery Insights

Widgets:
- Discovery friction rate trend (90-day rolling)
- Top friction themes (cluster labels)
- Feature mentions heatmap (which features are discussed most)
- Discovery-related cluster list with sizes

### Page 3: JTBD Map

Widgets:
- Table of all JTBD profiles (job statement, satisfaction score, gap)
- Gap analysis chart (sorted by gap_score)
- Cluster evidence for each JTBD (expandable)

### Page 4: Opportunity List

Widgets:
- Ranked table: title, opportunity_score, frequency, severity, segment
- Confidence distribution
- Filter by: segment, trend, discovery-related
- Click → Evidence Viewer

### Page 5: Segment Explorer

Widgets:
- User segment breakdown (power / casual / new / churned)
- Per-segment: discovery friction rate, top complaints, top JTBD
- Cross-segment comparison

### Page 6: NL Query Interface

- Text input box
- Query results panel (answer + key findings)
- Evidence panel (verbatims with review metadata)
- Export button (JSON / Markdown)

### Page 7: Evidence Viewer

- Input: insight_id or cluster_id
- Shows: title, description, confidence, reasoning
- Shows: all supporting verbatims with platform + date + rating
- Shows: full lineage (insight → cluster → analyzed_review → raw_review)

---

## Report Templates

### Executive Summary Report

```markdown
# Spotify Discovery Intelligence — Executive Summary
**Generated:** {date}
**Reviews Analyzed:** {count}
**Analysis Period:** {start} to {end}

## Top 5 Product Opportunities

1. **{title}** (Score: {score})
   - Affected Segment: {segment}
   - Frequency: {freq}% of reviews
   - Severity: {severity_label}
   - Key Finding: {description}
   - Evidence: "{verbatim}"

...

## Key Jobs To Be Done

| Job Statement | Satisfaction | Gap |
|---|---|---|
...

## Discovery Friction Summary

{discovery_friction_rate}% of reviews mention difficulty discovering new music.
Trend: {trend_direction} over last 90 days.
```

### Opportunity List Report (JSON)

Full ranked list with:
- All ProductInsight fields
- Supporting verbatims
- Lineage to cluster IDs
- Export timestamp

---

## API Layer

A lightweight API allows programmatic access to the knowledge base:

```python
GET /api/insights                          # All insights, sortable
GET /api/insights/{id}                     # Single insight with evidence
GET /api/insights/{id}/evidence            # Verbatims for an insight
GET /api/clusters                          # All clusters
GET /api/clusters/{id}/reviews             # Reviews in a cluster
GET /api/jtbd                              # All JTBD profiles
GET /api/segments                          # User segment profiles
POST /api/query                            # NL query endpoint
  body: {"question": "string"}
  returns: QueryAnswer
```

---

## Directory Structure

```
phase-7-query-reporting/
├── README.md                       ← This file
├── query-engine/
│   ├── __init__.py
│   ├── intent_classifier.py        ← Maps question → query intent
│   ├── query_planner.py            ← Builds query plan from intent
│   ├── query_executor.py           ← Runs DB + vector queries
│   ├── evidence_retriever.py       ← Fetches verbatims for results
│   └── answer_synthesizer.py       ← LLM answer generation
├── dashboards/
│   ├── __init__.py
│   ├── app.py                      ← Streamlit main app
│   ├── pages/
│   │   ├── 01_overview.py
│   │   ├── 02_discovery_insights.py
│   │   ├── 03_jtbd_map.py
│   │   ├── 04_opportunity_list.py
│   │   ├── 05_segment_explorer.py
│   │   ├── 06_nl_query.py
│   │   └── 07_evidence_viewer.py
│   └── components/
│       ├── insight_card.py
│       ├── evidence_panel.py
│       └── verbatim_list.py
├── reports/
│   ├── __init__.py
│   ├── executive_summary.py        ← Markdown report generator
│   ├── opportunity_list.py         ← JSON/CSV export
│   ├── jtbd_report.py
│   └── templates/
│       └── executive_summary.md.j2
├── api/
│   ├── __init__.py
│   └── routes.py                   ← FastAPI route definitions
├── tests/
│   ├── test_intent_classifier.py
│   ├── test_query_planner.py
│   ├── test_answer_synthesizer.py
│   └── test_report_generators.py
└── run_dashboard.py                ← Entry point: launches Streamlit
```

---

## Answer Synthesizer Prompt v1.0

```
You are an internal AI research assistant for a Product Manager at Spotify.

The PM asked: "{question}"

Here is the relevant data retrieved from the knowledge base:

Insights:
{insights_json}

Supporting Evidence:
{evidence_json}

Answer the question concisely and accurately.
- Reference specific evidence (quote reviews where helpful)
- State your confidence level
- Highlight any caveats or limitations in the data
- Do not speculate beyond what the evidence supports

Format your response as JSON:
{
  "answer": "prose answer",
  "confidence": "high|medium|low",
  "key_findings": [...],
  "caveats": "string or null"
}
```

---

## Testing Strategy

| Test Type | Coverage |
|---|---|
| Unit | IntentClassifier correctly routes known questions |
| Unit | QueryPlanner generates valid query plans |
| Unit | Report generators produce valid Markdown/JSON |
| Integration | Full NL query returns answer with evidence |
| Manual | Dashboard renders all pages without errors |
| Manual | PM scenario: answer "Why is discovery repetitive?" |

---

## Success Criteria

A Product Manager can ask:
- "Why do users repeatedly listen to the same content?"
- "Which user segments struggle most with discovering niche artists?"
- "What are the top 5 product opportunities?"

And receive:
- A clear, evidence-backed prose answer
- Supporting verbatims from real reviews
- Confidence level
- Traceable lineage to source reviews

All within 30 seconds of query submission.

---

## Dependencies

- `streamlit` — Dashboard UI
- `fastapi` — API layer
- `anthropic` — Answer synthesis
- `chromadb` — Vector search
- `jinja2` — Report templating
- `pandas` — Data manipulation for dashboard widgets
- `plotly` — Charts

---

## Phase 7 External Interface

This is the final output layer. All outputs must satisfy the system's core principle:

> Every recommendation, opportunity, or conclusion must remain traceable to the customer evidence that produced it.

No dashboard widget, API response, or report may present a finding without an associated `supporting_review_ids` or `verbatims` field.
