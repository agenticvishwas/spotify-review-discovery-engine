# Testing & Evaluation Skills

**Version:** 1.0
**Purpose:** Define the testing philosophy, evaluation framework, quality gates, and continuous validation process for AI-powered product research systems.

**Applies To:**

* Data ingestion
* Review preprocessing
* LLM pipelines
* Classification
* JTBD inference
* Theme clustering
* Insight generation
* Product opportunity discovery
* Dashboard outputs

---

# Mission

The objective is not merely to verify that the software works.

The objective is to ensure that the **AI system produces reliable, explainable, and actionable product intelligence**.

Every AI capability must have a measurable quality standard.

---

# Testing Philosophy

AI systems cannot be tested like traditional software alone.

A complete evaluation strategy combines:

* Software correctness
* Data quality
* Prompt quality
* Model quality
* Product usefulness
* Human validation

Every layer contributes to overall system quality.

---

# Evaluation Pyramid

```text
Business Impact
        ▲
Product Insights
        ▲
LLM Reasoning
        ▲
Structured Extraction
        ▲
Data Quality
        ▲
Software Reliability
```

Failures at lower levels propagate upward.

Fix lower layers before tuning higher ones.

---

# Quality Principles

Every evaluation should be:

* Repeatable
* Evidence-based
* Versioned
* Automated where possible
* Human-reviewable
* Independent of a single model

Avoid subjective "looks good" assessments.

---

# Testing Levels

## Level 1 — Data Quality

Validate incoming data.

Checks:

* Required fields present
* Encoding valid
* Language detected
* Duplicate reviews removed
* Missing values handled
* Timestamps normalized

Bad input leads to unreliable AI outputs.

---

## Level 2 — Schema Validation

Every intermediate output must conform to its schema.

Validate:

* JSON structure
* Required fields
* Allowed enums
* Numeric ranges
* Null handling

Reject invalid outputs before downstream processing.

---

## Level 3 — Prompt Validation

Verify that prompts consistently:

* Follow instructions
* Produce valid schemas
* Preserve evidence
* Report confidence
* Avoid unsupported fields

Prompts should behave predictably across representative datasets.

---

## Level 4 — Classification Evaluation

Evaluate each classifier independently.

Examples:

* Sentiment
* Emotion
* Recommendation issue
* User segment
* JTBD
* Listening behavior

Metrics:

* Accuracy
* Precision
* Recall
* F1 Score

Use labeled benchmark datasets whenever available.

---

## Level 5 — Clustering Evaluation

Measure cluster quality.

Metrics:

* Cluster purity
* Silhouette score (if applicable)
* Theme consistency
* Human agreement
* Duplicate separation

Clusters should remain stable as new data is added.

---

## Level 6 — Insight Evaluation

Assess whether generated insights are:

* Evidence-backed
* Actionable
* Explainable
* Segment-aware
* Business-relevant

Use a structured review rubric rather than subjective opinions.

---

## Level 7 — End-to-End Evaluation

Validate the complete workflow.

```text
Reviews
      ↓
Extraction
      ↓
Classification
      ↓
Clustering
      ↓
Insight Generation
      ↓
Opportunity Discovery
      ↓
Dashboard
```

The final output should remain traceable to the original reviews.

---

# Golden Evaluation Dataset

Maintain a curated dataset that represents common and difficult cases.

Include:

* Positive reviews
* Negative reviews
* Mixed sentiment
* Sarcasm
* Multilingual reviews
* Feature requests
* Duplicate reviews
* Ambiguous feedback
* Recommendation complaints
* Discovery success stories

Do not evaluate only on ideal inputs.

---

# Regression Dataset

Whenever a bug is fixed:

1. Add the review(s) to the regression dataset.
2. Document the expected output.
3. Ensure future prompt or model updates do not reintroduce the issue.

Regression datasets should grow continuously.

---

# Human Evaluation

Some tasks require expert judgment.

Review:

* JTBD quality
* Root cause inference
* Theme labels
* Insight usefulness
* Opportunity quality

Record reviewer agreement to improve consistency.

---

# Evaluation Metrics

Track metrics at multiple levels.

## Data

* Duplicate rate
* Missing field rate
* Language detection accuracy

## Prompt

* Valid JSON rate
* Retry rate
* Average token usage
* Prompt latency

## AI

* Classification accuracy
* Hallucination rate
* Confidence calibration
* Human agreement

## Product

* Insight usefulness
* Recommendation quality
* Opportunity relevance
* Executive satisfaction

Measure both technical quality and business value.

---

# Confidence Calibration

Confidence scores should reflect actual reliability.

Example:

A confidence of 0.90 should be correct approximately 90% of the time over representative datasets.

Overconfident AI systems reduce trust.

---

# Hallucination Detection

Monitor for:

* Unsupported facts
* Invented user behaviors
* Imaginary product features
* Fabricated statistics
* Incorrect causal relationships

Require supporting evidence for every generated insight.

---

# Failure Analysis

When evaluation fails:

1. Identify the layer where the failure occurred.
2. Determine whether the issue is:

   * Data
   * Prompt
   * Model
   * Schema
   * Business logic
3. Fix the root cause.
4. Add a regression test.
5. Re-run the evaluation suite.

Never patch symptoms without understanding the cause.

---

# Performance Benchmarks

Track:

* Average latency
* Reviews processed per minute
* Token consumption
* API cost per review
* Memory usage
* Batch throughput

Performance improvements should not reduce analytical quality.

---

# Acceptance Criteria

Before promoting a workflow:

* All schemas validate.
* No critical prompt failures.
* Required evaluation metrics meet thresholds.
* Human review confirms acceptable quality.
* Regression suite passes.
* Documentation is updated.

---

# Continuous Evaluation

Evaluation is continuous.

Every change to:

* Prompt
* Model
* Taxonomy
* Schema
* Pipeline

must trigger re-evaluation.

Do not assume improvements generalize.

---

# Testing Checklist

For every release verify:

* Data quality checks pass.
* Schemas validate.
* Prompts produce expected outputs.
* Benchmark dataset passes.
* Regression dataset passes.
* Confidence scores remain calibrated.
* Insights remain traceable.
* Performance targets are met.
* Documentation reflects changes.

---

# Common Anti-Patterns

Avoid:

* Testing only happy paths.
* Evaluating on tiny datasets.
* Ignoring multilingual reviews.
* Measuring accuracy without business usefulness.
* Trusting confidence scores without calibration.
* Updating prompts without regression testing.
* Declaring success based on anecdotal examples.

---

# Definition of Done

An AI capability is production-ready only when:

* Data quality is validated.
* Intermediate outputs conform to schemas.
* Prompts meet evaluation thresholds.
* Benchmark and regression datasets pass.
* Human reviewers agree the outputs are useful.
* Insights are evidence-backed and traceable.
* Performance is within acceptable limits.
* Documentation and evaluation reports are complete.

---

# Guiding Principle

> **An AI system is not trustworthy because it generates impressive outputs. It is trustworthy because its behavior is measurable, reproducible, continuously evaluated, and grounded in customer evidence.**
