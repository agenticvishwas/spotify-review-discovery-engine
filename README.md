# Spotify Review Discovery Engine

An AI-powered Voice of Customer platform that transforms large-scale Spotify user feedback into structured, evidence-backed product intelligence for Product Managers.

---

## System Purpose

Product Managers spend days reading reviews and synthesizing insights manually. This system compresses that work into minutes by running a 7-phase AI pipeline that converts raw reviews into ranked product opportunities — all traceable back to the original customer evidence.

---

## 7-Phase Architecture

```
Phase 1  →  Phase 2  →  Phase 3  →  Phase 4  →  Phase 5  →  Phase 6  →  Phase 7
Ingest   →  Clean    →  Analyze  →  Cluster  →  Insights →  Store    →  Query
```

| Phase | Folder | Purpose | AI? |
|---|---|---|---|
| 1 | [phase-1-data-ingestion/](phase-1-data-ingestion/) | Collect raw reviews from 5 platforms | No |
| 2 | [phase-2-preprocessing/](phase-2-preprocessing/) | Clean, deduplicate, normalize text | No |
| 3 | [phase-3-ai-analysis/](phase-3-ai-analysis/) | Per-review LLM extraction of signals | Yes |
| 4 | [phase-4-clustering/](phase-4-clustering/) | Semantic clustering + theme labeling | Yes |
| 5 | [phase-5-insight-generation/](phase-5-insight-generation/) | JTBD, opportunities, unmet needs | Yes |
| 6 | [phase-6-storage/](phase-6-storage/) | Persist all data to DB + vector store | No |
| 7 | [phase-7-query-reporting/](phase-7-query-reporting/) | NL query, dashboards, reports | Yes |

---

## Key Design Principles

1. **Evidence Over Opinion** — every insight links to source reviews
2. **Structure Before Summaries** — JSON schemas defined before LLM calls
3. **Explainability** — confidence scores on every AI output
4. **Human-in-the-Loop** — system surfaces evidence; PM decides
5. **Modularity** — each phase runs independently
6. **Deterministic Where Possible** — AI only where semantic reasoning is required

---

## Data Lineage Contract

Every record carries a traceable chain from raw review to final insight:

```
RawReview → NormalizedReview → AnalyzedReview → ReviewCluster → ProductInsight → Report
```

This lineage is non-negotiable. Every PM-facing answer includes source review IDs.

---

## Success Definition

A Product Manager can ask:

> "Why do users repeatedly listen to the same content?"

And receive a structured, evidence-backed answer with verbatim quotes from real reviews — in under 30 seconds.

---

## Documentation

- [Master Architecture](docs/architecture/ARCHITECTURE.md)
- [Architecture Decisions](docs/architecture/phase-decisions.md)
- [Problem Statement](docs/problemStatement.md)

---

## Technology Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11+ |
| LLM | Anthropic Claude (claude-sonnet-4-6) |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| Vector DB | ChromaDB |
| Relational DB | SQLite → PostgreSQL |
| Clustering | HDBSCAN |
| Dashboard | Streamlit |
| Testing | pytest |
"# spotify-review-discovery-engine" 
"# spotify-review-discovery-engine" 
