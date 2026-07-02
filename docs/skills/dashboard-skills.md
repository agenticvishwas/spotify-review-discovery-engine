# Dashboard Skills

**Version:** 2.0 (Product Intelligence Dashboard Operating Manual)

**Purpose**

Define how AI-generated product intelligence should be transformed into dashboards that enable Product Managers, Growth teams, Designers, Data Scientists, and Executives to make faster, evidence-backed decisions.

A dashboard is not a reporting tool.

A dashboard is a decision support system.

---

# Mission

Your responsibility is **not** to build attractive dashboards.

Your responsibility is to reduce the time required to answer product questions.

Every dashboard should help someone make a better decision within five minutes.

If a dashboard creates more questions than answers, it has failed.

---

# Dashboard Philosophy

Dashboards exist to answer decisions.

Not display metrics.

Every dashboard must answer one of:

* What happened?
* Why did it happen?
* Who is affected?
* What should we do?
* How confident are we?
* What evidence supports this?

Anything that doesn't help answer these questions is noise.

---

# Dashboard Hierarchy

Every dashboard should follow the same reasoning hierarchy.

```text
Raw Reviews
      ↓
Signals
      ↓
Patterns
      ↓
Themes
      ↓
Insights
      ↓
Root Causes
      ↓
Opportunities
      ↓
Recommendations
      ↓
Experiments
```

Users should never need to jump between unrelated dashboards.

---

# Decision-First Design

Before adding any visualization ask:

**What decision does this enable?**

If no decision exists,

do not build it.

Examples:

❌ Average sentiment

✅ Which recommendation issues are increasing fastest?

---

# The Five-Layer Dashboard

Every Product Intelligence dashboard should be organized into five layers.

---

## Layer 1 — Executive Summary

Purpose:

Allow an executive to understand platform health within 30 seconds.

Include:

* Top product opportunities
* Critical customer issues
* Emerging trends
* Opportunity score
* Confidence score
* Business impact

No implementation details.

---

## Layer 2 — Product Intelligence

Purpose:

Help Product Managers understand customer problems.

Show:

* Top frustrations
* JTBD
* Root causes
* Listening behaviors
* Recommendation failures
* Segment comparisons

Focus on why.

Not just what.

---

## Layer 3 — Evidence Explorer

Every insight must be explainable.

Selecting any insight should reveal:

Supporting reviews

↓

Theme clusters

↓

Original review

↓

Source platform

↓

Confidence

↓

Reasoning chain

Every conclusion must be traceable.

---

## Layer 4 — Opportunity Workspace

Convert research into action.

Every opportunity should display:

Problem

↓

Customer Need

↓

Affected Segment

↓

Evidence

↓

Business Value

↓

Effort

↓

Confidence

↓

Suggested Experiment

This is where roadmap discussions begin.

---

## Layer 5 — AI Diagnostics

The AI should explain itself.

Display:

Pipeline health

Prompt versions

Model versions

Confidence distribution

Hallucination rate

Validation failures

Schema failures

Token usage

Latency

Engineers should trust the pipeline before trusting the insights.

---

# Dashboard Navigation

Users should navigate naturally.

```text
Overview

↓

Insight

↓

Theme

↓

Cluster

↓

Review

↓

Original Source
```

Never force users to search manually for supporting evidence.

---

# Information Hierarchy

Organize content from highest value to lowest.

Business Outcomes

↓

Customer Problems

↓

Insights

↓

Evidence

↓

Raw Data

Do not reverse this order.

---

# Progressive Disclosure

Reveal complexity gradually.

Level 1

Executive summary

↓

Level 2

Product insights

↓

Level 3

Supporting evidence

↓

Level 4

Raw reviews

Most users should never need Level 4.

---

# Dashboard Questions

Every dashboard should immediately answer:

What changed?

Why?

Who is affected?

How serious is it?

What evidence exists?

What should we do?

How confident is the recommendation?

Which experiment should run next?

---

# Opportunity Ranking

Every opportunity should include:

Opportunity Score

Customer Impact

Business Alignment

Evidence Strength

Confidence

Engineering Effort

Learning Value

Avoid ranking solely by frequency.

---

# Confidence Visualization

Every AI-generated insight should expose confidence.

Example:

High Confidence

92%

Evidence

184 Reviews

Platforms

App Store

Play Store

Community

Never hide uncertainty.

---

# Segment Explorer

Every dashboard should support filtering by:

* New users
* Premium
* Free
* Region
* Device
* Listening frequency
* Genre preference
* Music discovery behavior

Insights without segmentation are incomplete.

---

# Trend Intelligence

Track:

New issues

Growing issues

Stable issues

Resolved issues

Seasonal behavior

Emerging opportunities

Trend direction matters more than snapshots.

---

# JTBD Dashboard

Present customer jobs rather than feature requests.

Example:

Customer Job

↓

Current Friction

↓

Existing Workaround

↓

Opportunity

↓

Potential Product Direction

JTBD should become a first-class dashboard entity.

---

# Root Cause Explorer

Every major issue should expose:

Observed Problem

↓

Contributing Factors

↓

Evidence

↓

Likely Root Cause

↓

Confidence

↓

Affected Segments

↓

Business Impact

Avoid superficial issue reporting.

---

# Recommendation Center

The dashboard should never stop at insights.

Every major insight should generate:

Recommended Experiment

Expected Outcome

Success Metrics

Dependencies

Risks

Confidence

Decision Status

Insights without actions are incomplete.

---

# Explainable AI

Users should understand why AI generated an insight.

Every recommendation should display:

Evidence

↓

Reasoning Summary

↓

Supporting Themes

↓

Confidence

↓

Source Reviews

Transparency builds trust.

---

# Dashboard Performance

Optimize for:

Time to Insight

Time to Decision

Navigation Depth

Click Efficiency

Cognitive Load

Information Density

A dashboard should reduce thinking effort—not increase it.

---

# Dashboard Anti-Patterns

Avoid:

Too many charts

Pie charts for everything

Hidden assumptions

No drill-down

No evidence

Vanity metrics

Metric overload

Static screenshots

Disconnected dashboards

AI outputs without explanations

Dashboards that answer "what" but not "why"

---

# Dashboard Review Checklist

Before publishing verify:

✓ Every widget supports a decision.

✓ Every insight links to evidence.

✓ Confidence is visible.

✓ Segments are supported.

✓ Trends are visible.

✓ Opportunities are prioritized.

✓ Experiments are suggested.

✓ AI reasoning is explainable.

✓ Navigation is intuitive.

✓ Executive summary exists.

---

# Definition of Done

A Product Intelligence dashboard is complete only when:

It enables product decisions.

Insights are evidence-backed.

Every conclusion is traceable.

Customer segments are supported.

Root causes are visible.

Opportunities are prioritized.

Experiments are proposed.

Confidence is communicated.

The dashboard reduces decision time.

Users can move from executive summary to raw evidence without leaving the system.

---

# Dashboard Maturity Model

```text
Level 1
Reporting Dashboard

↓

Level 2
Analytics Dashboard

↓

Level 3
Insight Dashboard

↓

Level 4
Decision Dashboard

↓

Level 5
AI Product Intelligence Platform
```

The goal is **Level 5**.

---

# Guiding Principle

> **A dashboard is successful not when it displays every metric, but when it enables the right person to make the right product decision, with the right evidence, in the shortest possible time. Every visualization should reduce uncertainty, increase confidence, and lead naturally to the next action.**
