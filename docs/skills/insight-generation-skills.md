# Insight Generation Skills

**Version:** 1.0
**Purpose:** Transform structured customer feedback into evidence-backed product insights, opportunities, and strategic recommendations.

**Applies To:**

* Product Research
* Voice of Customer Analysis
* AI-powered Insight Generation
* Product Strategy
* Growth Teams
* Executive Reporting

---

# Mission

Your responsibility is **not** to summarize data.

Your responsibility is to discover meaningful patterns that explain customer behavior and help Product Managers make better decisions.

An insight should reduce uncertainty.

If it doesn't influence a product decision, it is not a useful insight.

---

# Insight Generation Philosophy

Data becomes information.

Information becomes knowledge.

Knowledge becomes insight.

Insight becomes action.

Always progress through these stages.

Never jump directly from data to recommendations.

---

# Insight Maturity Model

```text
Raw Reviews
      ↓
Structured Facts
      ↓
Observed Patterns
      ↓
Validated Themes
      ↓
Customer Insights
      ↓
Root Causes
      ↓
Product Opportunities
      ↓
Strategic Recommendations
      ↓
Experiments
```

Each stage should build upon validated evidence from the previous stage.

---

# Golden Rule

Insights must emerge from **multiple independent customer signals**, not isolated anecdotes.

Never elevate a single review into a strategic insight.

---

# The Anatomy of a High-Quality Insight

Every insight must answer:

1. What is happening?
2. Who is affected?
3. Why is it happening?
4. Why does it matter?
5. How frequently does it occur?
6. What evidence supports it?
7. What business objective is impacted?
8. What opportunity does it reveal?

If any of these questions cannot be answered, the insight is incomplete.

---

# Insight Pipeline

```text
Reviews
      ↓
Facts
      ↓
Evidence
      ↓
Patterns
      ↓
Themes
      ↓
Hypotheses
      ↓
Validation
      ↓
Insights
      ↓
Opportunities
      ↓
Recommendations
```

Avoid skipping validation.

---

# Step 1 — Pattern Discovery

Look for recurring signals across reviews.

Examples:

* repeated complaints
* repeated feature requests
* repeated workarounds
* repeated listening behaviors
* repeated recommendation failures

Focus on recurrence rather than novelty.

---

# Step 2 — Theme Consolidation

Merge related patterns into stable themes.

Example:

Patterns

* Same artists recommended
* Same playlists suggested
* Similar songs repeated

↓

Theme

Recommendation Repetition

Themes should remain stable as new data arrives.

---

# Step 3 — Evidence Validation

Every theme must be supported by:

* Review count
* Frequency
* Representative quotes
* Multiple sources
* Time distribution
* Confidence score

Do not rely on anecdotal evidence.

---

# Step 4 — Customer Insight

Translate validated themes into customer understanding.

Poor insight

> Users dislike recommendations.

Strong insight

> Active music explorers perceive recommendation quality as repetitive because historical listening behavior dominates exploration, reducing exposure to unfamiliar artists.

The second explains **why**, not just **what**.

---

# Step 5 — Root Cause Discovery

Use structured reasoning to identify plausible causes.

Framework:

Observed Pattern

↓

Possible Causes

↓

Supporting Evidence

↓

Most Likely Root Cause

↓

Confidence

Distinguish between symptoms and underlying mechanisms.

---

# Step 6 — Opportunity Identification

Every validated insight should lead to one or more product opportunities.

Framework:

Problem

↓

Need

↓

Opportunity

↓

Desired Outcome

↓

Potential Solutions

Avoid proposing features before understanding the opportunity.

---

# Opportunity Categories

Classify opportunities consistently.

Examples:

* Discovery Experience
* Personalization
* Recommendation Diversity
* User Education
* Search & Navigation
* Playlist Management
* Artist Exploration
* Social Discovery
* Context Awareness
* Trust & Transparency

Maintain a shared taxonomy.

---

# Opportunity Prioritization

Evaluate opportunities using:

* Customer impact
* Problem severity
* Frequency
* Strategic alignment
* Technical feasibility
* Confidence
* Learning potential

Prioritization should be transparent and evidence-backed.

---

# Insight Confidence

Every insight should include:

```json
{
  "confidence": 0.91,
  "evidence_strength": "High",
  "review_count": 184,
  "sources": [
    "App Store",
    "Play Store",
    "Community Forum"
  ]
}
```

Confidence reflects evidence quality—not model certainty alone.

---

# Contradictory Evidence

Not all users experience the same problems.

When evidence conflicts:

* Preserve both viewpoints.
* Identify affected user segments.
* Quantify the distribution.
* Explain possible reasons.

Avoid forcing consensus.

---

# Segment-Aware Insights

Never assume one insight applies to all users.

Segment by:

* Listening behavior
* Subscription type
* Experience level
* Geography
* Music preferences
* Usage frequency

Insights become more actionable when tied to specific user groups.

---

# Trend Analysis

Track how themes evolve over time.

Measure:

* Growth
* Decline
* Seasonality
* Emerging issues
* Resolved problems

An emerging issue may deserve attention before it becomes widespread.

---

# Executive-Level Insights

Executive insights should answer:

* What's changing?
* Why does it matter?
* What should we do?
* What is the expected business impact?
* What evidence supports this recommendation?

Avoid operational details in executive summaries.

---

# Storytelling Framework

Present findings using a consistent narrative.

```text
Customer Problem
      ↓
Evidence
      ↓
Pattern
      ↓
Insight
      ↓
Root Cause
      ↓
Opportunity
      ↓
Recommendation
      ↓
Experiment
      ↓
Success Metric
```

A good story connects evidence to action.

---

# Insight Quality Checklist

Every insight should be:

* Evidence-backed
* Reproducible
* Explainable
* Actionable
* Segment-aware
* Confidence-scored
* Linked to business goals
* Traceable to source reviews

---

# Common Anti-Patterns

Avoid:

* Reporting statistics without interpretation.
* Treating themes as insights.
* Confusing correlation with causation.
* Recommending solutions without validated problems.
* Ignoring contradictory evidence.
* Overgeneralizing from small samples.
* Hiding uncertainty.
* Generating insights without business context.

---

# Insight Evaluation Metrics

Measure:

* Insight usefulness
* Human agreement
* Actionability
* Traceability
* Novelty
* Stability over time
* Opportunity precision
* Recommendation quality

A high-quality insight should consistently support better product decisions.

---

# AI-Assisted Insight Generation

Use AI to:

* Synthesize large datasets.
* Identify semantic relationships.
* Generate hypotheses.
* Explain recurring patterns.

Do **not** use AI to invent evidence or replace human judgment.

AI augments product research; it does not replace product management.

---

# Deliverable Standards

Every generated insight should include:

* Insight title
* Summary
* Supporting evidence
* Affected user segments
* Root cause
* Opportunity
* Confidence
* Business impact
* Suggested experiment
* Success metrics

The output should be immediately usable in a product review meeting.

---

# Definition of Done

An insight is complete only when:

* It is grounded in validated evidence.
* It explains both the problem and the underlying cause.
* It identifies the affected users.
* It quantifies confidence.
* It reveals a meaningful product opportunity.
* It supports a measurable business outcome.
* It can inform a product decision or experiment.

---

# Guiding Principle

> **An insight is not a summary of what customers said. It is an evidence-backed explanation of why customers behave the way they do, why that matters to the business, and what product opportunity it creates.**
