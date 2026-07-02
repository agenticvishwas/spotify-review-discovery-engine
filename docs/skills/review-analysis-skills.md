# Review Analysis Skills

**Version:** 1.0
**Purpose:** Domain Skill for AI-powered Voice of Customer Analysis
**Applies To:** App Store Reviews, Play Store Reviews, Community Forums, Reddit, Social Media, Product Feedback

---

# Mission

Your responsibility is **not** to summarize customer reviews.

Your responsibility is to transform large volumes of unstructured customer feedback into structured, evidence-backed product intelligence that enables Product Managers to make informed decisions.

Every review is a data point.

The objective is to discover patterns, explain user behavior, identify unmet needs, and uncover opportunities for product improvement.

---

# Product Research Philosophy

Reviews are symptoms.

Product problems are causes.

Opportunities are solutions.

Always analyze beyond the surface.

Instead of asking:

> "What did the user say?"

Ask:

* Why did they say it?
* What were they trying to accomplish?
* What prevented success?
* How common is this problem?
* Which users experience it?
* What opportunity does it reveal?

---

# Review Intelligence Pipeline

Every review should progress through the same analytical workflow.

```text
Raw Review
      ↓
Normalization
      ↓
Structured Extraction
      ↓
Classification
      ↓
Intent Detection
      ↓
JTBD Inference
      ↓
Root Cause Analysis
      ↓
Theme Assignment
      ↓
Cluster Formation
      ↓
Opportunity Mapping
      ↓
Evidence-backed Insight
```

Never skip intermediate reasoning steps.

---

# Golden Rule

Never analyze reviews in isolation.

Every review contributes to a broader pattern.

The unit of product insight is **the cluster**, not the individual review.

---

# Stage 1 — Review Normalization

Before AI reasoning:

Normalize:

* spelling
* emojis
* punctuation
* duplicated content
* language
* encoding
* timestamps

Preserve the original review separately.

Never overwrite source data.

---

# Stage 2 — Atomic Complaint Extraction

One review may contain multiple complaints.

Example:

> "Recommendations are repetitive and the app crashes while playing podcasts."

Extract separately:

Complaint 1

Recommendation repetition

Complaint 2

Playback stability

Never force one review into one category.

---

# Stage 3 — Structured Review Schema

Every review should be converted into structured data.

Required fields:

```json
{
  "review_id": "",
  "source": "",
  "rating": 0,
  "language": "",
  "summary": "",
  "sentiment": "",
  "emotion": "",
  "complaints": [],
  "feature_mentions": [],
  "recommendation_issues": [],
  "listening_behavior": "",
  "user_segment": "",
  "job_to_be_done": "",
  "root_cause": "",
  "unmet_need": "",
  "confidence": 0.0
}
```

Never produce partial schemas.

---

# Stage 4 — Sentiment Analysis

Sentiment is multidimensional.

Classify:

* Overall sentiment
* Product sentiment
* Feature sentiment
* Recommendation sentiment
* Discovery sentiment

Do not rely solely on positive / negative / neutral.

Capture nuance.

---

# Stage 5 — Emotion Detection

Infer dominant emotions.

Examples:

* Frustration
* Confusion
* Delight
* Curiosity
* Trust
* Disappointment
* Surprise
* Hope

Emotion explains why users behave the way they do.

---

# Stage 6 — Intent Detection

Identify what users are trying to achieve.

Example intents:

* Discover new artists
* Escape repetitive playlists
* Find workout music
* Improve recommendations
* Explore regional music
* Reduce search effort
* Listen by mood

Intent is often implicit.

Infer it using context.

---

# Stage 7 — Jobs To Be Done (JTBD)

Translate complaints into customer jobs.

Example:

Complaint:

> "Spotify keeps recommending the same artists."

JTBD:

> Help me effortlessly discover unfamiliar artists without sacrificing relevance.

Focus on the user's desired progress, not the requested feature.

---

# Stage 8 — Recommendation Issue Taxonomy

Classify recommendation-related problems using a consistent taxonomy.

Examples:

* Artist repetition
* Song repetition
* Playlist repetition
* Popularity bias
* Genre tunnel
* Weak diversity
* Poor personalization
* Over-personalization
* Cold-start recommendations
* Context mismatch
* Mood mismatch
* Regional mismatch
* Language mismatch
* Temporal mismatch

Never invent new labels unless justified and documented.

---

# Stage 9 — Listening Behavior Classification

Infer listening behavior.

Examples:

* Passive listener
* Active explorer
* Mood listener
* Commuter
* Workout listener
* Focus listener
* Album enthusiast
* Playlist curator
* Podcast-heavy user

Behavior should be inferred from evidence, not stereotypes.

---

# Stage 10 — User Segmentation

Estimate likely user segments.

Possible segments:

* New user
* Returning user
* Premium subscriber
* Free-tier listener
* Heavy listener
* Casual listener
* Student
* Audiophile
* Regional music fan
* Independent artist supporter

Segmentation is probabilistic.

Report confidence.

---

# Stage 11 — Root Cause Analysis

Separate symptoms from causes.

Example:

Symptom:

Repeated recommendations

Possible root causes:

* Reinforcement loop
* Limited exploration
* Popularity bias
* Sparse listening history
* Weak contextual signals

Root causes should explain recurring patterns across many reviews.

---

# Stage 12 — Theme Clustering

Cluster semantically related reviews.

A valid cluster contains:

* Theme name
* Description
* Supporting review IDs
* Frequency
* Representative quotes
* Average sentiment
* Severity
* Confidence

Clusters should evolve as new reviews arrive.

---

# Stage 13 — Opportunity Mapping

Translate validated problems into product opportunities.

Framework:

Problem

↓

User Need

↓

Opportunity

↓

Potential Product Direction

Example:

Problem

Recommendations repeat.

↓

Need

More discovery diversity.

↓

Opportunity

Introduce adjustable exploration controls.

Do not prescribe detailed solutions prematurely.

---

# Handling Ambiguity

Some reviews are:

* sarcastic
* contradictory
* vague
* multilingual
* emotionally mixed

In these cases:

* reduce confidence
* preserve ambiguity
* avoid over-classification
* surface for human review when needed

Never fabricate certainty.

---

# Evidence Standards

Every insight must be supported by evidence.

Maintain:

* Review IDs
* Source platform
* Frequency
* Representative quotes
* Confidence
* Timestamp

Insights without evidence should not appear in reports.

---

# Quality Checklist

For every processed review verify:

* Structured schema complete
* Multiple complaints extracted
* Intent identified
* JTBD inferred
* Recommendation issue classified
* Listening behavior estimated
* User segment estimated
* Root cause inferred
* Confidence assigned
* Evidence preserved

---

# Common Anti-Patterns

Avoid:

* One-label classification
* Free-text summaries only
* Ignoring mixed sentiment
* Assuming intent without evidence
* Overfitting to individual reviews
* Creating clusters from too few examples
* Confusing feature requests with underlying needs
* Jumping directly from complaint to solution

---

# Review Analysis Success Metrics

Measure the quality of the analysis using:

* Classification accuracy
* Theme consistency
* Cluster purity
* Human agreement
* Coverage of extracted complaints
* JTBD quality
* Root cause precision
* Confidence calibration
* Insight traceability

Review quality should improve over time through prompt refinement and evaluation.

---

# Definition of Done

A review analysis workflow is complete when:

* Every review has been normalized.
* Atomic complaints have been extracted.
* Structured metadata has been generated.
* JTBD and user intent have been inferred.
* Themes and clusters have been updated.
* Evidence remains traceable.
* Product opportunities are grounded in recurring patterns.
* Confidence is reported for all inferred fields.
* Outputs are suitable for downstream aggregation and dashboarding.

---

# Guiding Principle

> **Do not build a review summarizer. Build a system that converts customer conversations into structured product knowledge. Every insight should be explainable, measurable, and directly traceable to the users who inspired it.**
