# Architecture Decision Record — Phase-Wise Design

**Version:** 1.0
**Status:** Active

---

## ADR-001: Why 7 Phases?

**Context:** The system must convert raw reviews into PM-facing insights. Multiple decompositions were possible.

**Decision:** Separate into 7 phases along data transformation boundaries.

**Alternatives Considered:**

| Alternative | Trade-off |
|---|---|
| 3 phases: Ingest / Analyze / Report | Simpler, but AI analysis and clustering become tangled. Hard to debug or swap components. |
| Microservices from day one | Operationally expensive before product-market fit is established. |
| Single monolithic pipeline | Fast to write, impossible to maintain or partially re-run. |

**Rationale:** 7 phases align exactly with the data transformation stages: raw → clean → analyzed → clustered → insight → stored → queried. Each phase has a single responsibility, clear input/output contracts, and can be run and tested independently.

---

## ADR-002: Why JSONL as Inter-Phase Format?

**Decision:** Each phase writes JSONL files as its primary output. Downstream phases read JSONL.

**Alternatives:**

| Alternative | Trade-off |
|---|---|
| Direct database writes from each phase | Creates tight coupling between phases and the storage layer. |
| In-memory dataframes passed between phases | Cannot resume mid-pipeline after failures; no audit trail. |
| Parquet files | Better for analytics, but adds dependency and complexity for this use case. |

**Rationale:** JSONL is human-readable, appendable, schema-enforced at write time, and creates a natural audit trail. Each JSONL file is an immutable snapshot of what a phase produced, enabling replay and debugging.

---

## ADR-003: Why sentence-transformers instead of OpenAI Embeddings?

**Decision:** Use `all-MiniLM-L6-v2` (local) for embeddings.

**Alternatives:**

| Alternative | Trade-off |
|---|---|
| OpenAI text-embedding-ada-002 | Higher quality, but adds API cost per review and network dependency. |
| Anthropic embeddings | Not yet available as a standalone API. |
| TF-IDF / BM25 | Deterministic, but misses semantic similarity entirely. |

**Rationale:** For clustering purposes, `all-MiniLM-L6-v2` produces embeddings of sufficient quality at zero marginal cost. Reviews are short enough that model capacity is not a bottleneck. Local operation means no data leaves the environment.

---

## ADR-004: Why HDBSCAN over k-means?

**Decision:** Use HDBSCAN as primary clustering algorithm.

**Alternatives:**

| Alternative | Trade-off |
|---|---|
| k-means | Requires knowing k in advance; forces all points into clusters. |
| Agglomerative clustering | O(n²) memory — too slow for 10k+ reviews. |
| LDA (topic modeling) | Bag-of-words, misses semantic similarity; outputs topics not clusters. |

**Rationale:** HDBSCAN naturally handles the variable density of real-world review datasets. The explicit noise label (-1) allows graceful handling of uncategorizable reviews without distorting cluster quality. Does not require specifying the number of clusters upfront.

---

## ADR-005: Why SQLite → PostgreSQL Progression?

**Decision:** Start with SQLite in development; migrate to PostgreSQL for production.

**Alternatives:**

| Alternative | Trade-off |
|---|---|
| PostgreSQL from day one | Operational overhead before the schema stabilizes. |
| DynamoDB / NoSQL | Poor fit for the relational evidence-linking requirements. |
| Pure file-based (JSONL only) | Cannot support complex queries or joins across phases. |

**Rationale:** SQLite has zero operational cost and identical SQL syntax. The repository pattern in Phase 6 abstracts the database driver, so migration to PostgreSQL only requires changing the connection string, not the query logic.

---

## ADR-006: Why Streamlit for Dashboards?

**Decision:** Use Streamlit as the PM-facing dashboard framework.

**Alternatives:**

| Alternative | Trade-off |
|---|---|
| React + API | Full flexibility, but requires frontend engineering resources. |
| Metabase | Good for SQL dashboards; poor support for NL query or custom AI components. |
| Jupyter Notebooks | Good for exploration; poor for recurring PM use. |

**Rationale:** Streamlit enables rapid PM-facing UIs in pure Python without a separate frontend codebase. The NL query component and evidence viewer require custom logic that fits naturally in Python. Can be replaced with a React frontend later if scale demands it.

---

## ADR-007: Why Claude for LLM Analysis?

**Decision:** Use Anthropic Claude (claude-sonnet-4-6) as primary LLM.

**Alternatives:**

| Alternative | Trade-off |
|---|---|
| GPT-4o | Comparable quality; no strong reason to prefer it here. |
| Llama 3 (local) | Avoids API cost; lower reasoning quality on nuanced extraction. |
| Gemini | Comparable; Claude's structured output via tool_use is well-tested. |

**Rationale:** Claude's tool_use API enforces JSON schema compliance at the API level, eliminating the need for custom JSON parsing and retry logic for format errors. Excellent reasoning quality on nuanced sentiment and intent extraction tasks. claude-haiku-4-5 available for cost-sensitive first-pass runs.
