# Prompt Engineering Skills

**Version:** 1.0
**Purpose:** Design, implement, evaluate, and maintain production-quality prompts for AI-powered product research systems.
**Applies To:** Review classification, semantic extraction, clustering, JTBD inference, insight generation, opportunity discovery, report synthesis

---

# Mission

Prompts are software.

Treat every prompt as a production artifact with clear ownership, versioning, testing, documentation, and measurable quality.

The objective is not to produce clever prompts.

The objective is to build **predictable AI pipelines**.

---

# Prompt Engineering Philosophy

Every prompt should have **one responsibility**.

Avoid giant prompts that:

* classify
* summarize
* reason
* cluster
* recommend

simultaneously.

Instead, decompose work into independent reasoning stages.

Small prompts are easier to:

* debug
* evaluate
* improve
* replace
* version

---

# Prompt Lifecycle

Every prompt follows the same lifecycle.

```text
Problem
      ↓
Prompt Design
      ↓
Schema Definition
      ↓
Evaluation Dataset
      ↓
Implementation
      ↓
Testing
      ↓
Monitoring
      ↓
Refinement
      ↓
Version Upgrade
```

Prompts evolve through evidence, not intuition.

---

# Prompt Architecture

Separate prompts by responsibility.

```text
Review
      ↓
Extraction Prompt
      ↓
Classification Prompt
      ↓
JTBD Prompt
      ↓
Root Cause Prompt
      ↓
Clustering Prompt
      ↓
Insight Prompt
      ↓
Opportunity Prompt
      ↓
Executive Summary Prompt
```

Never merge unrelated reasoning tasks.

---

# Prompt Design Principles

Every prompt should:

* Have a single objective.
* Receive structured input.
* Produce structured output.
* State assumptions explicitly.
* Define constraints.
* Include evaluation criteria.
* Avoid unnecessary narrative.

Optimize for consistency over creativity.

---

# Prompt Contract

Each production prompt must include:

## Metadata

* Prompt Name
* Version
* Owner
* Purpose
* Last Updated

## Inputs

* Required fields
* Optional fields
* Expected schema

## Outputs

* JSON schema
* Confidence score
* Validation rules

## Failure Modes

* Missing data
* Ambiguous language
* Low confidence
* Unsupported language

---

# Structured Inputs

Provide context explicitly.

Bad

```text
Analyze this review.
```

Good

```text
Task:
Extract recommendation issues.

Context:
Spotify review.

Output:
Valid JSON.

Constraints:
No additional commentary.
```

Never rely on implicit context.

---

# Structured Outputs

Intermediate prompts should never return prose.

Preferred format:

```json
{
  "classification": "",
  "confidence": 0.94,
  "reasoning": "",
  "evidence": []
}
```

Narrative belongs only in the final reporting stage.

---

# Layered Prompting

Every stage should solve one reasoning problem.

Example:

Layer 1

Extract entities

↓

Layer 2

Identify complaints

↓

Layer 3

Infer JTBD

↓

Layer 4

Infer root causes

↓

Layer 5

Cluster reviews

↓

Layer 6

Generate insights

↓

Layer 7

Recommend opportunities

Each layer should consume the previous layer's structured output.

---

# Context Engineering

Provide only the context needed.

Preferred order:

1. System objective
2. Task description
3. Business context
4. Input data
5. Constraints
6. Output schema
7. Validation requirements

Avoid overwhelming the model with unnecessary information.

---

# Evidence-First Prompting

Ground every reasoning task in source data.

Instead of asking:

> Why do users dislike recommendations?

Ask:

> Based only on the supplied reviews, identify recurring recommendation issues and cite the supporting review identifiers.

Prompts should never encourage speculation.

---

# Chain of Reasoning

Separate reasoning from presentation.

Internal pipeline:

```text
Extract Facts
      ↓
Identify Patterns
      ↓
Infer Meaning
      ↓
Validate
      ↓
Generate Output
```

The final response should expose conclusions, not hidden reasoning.

---

# Prompt Templates

Every prompt should follow a reusable template.

```text
Role

Objective

Business Context

Task

Instructions

Constraints

Output Schema

Validation Rules
```

Avoid ad hoc prompt structures.

---

# Prompt Versioning

Every prompt must have a version.

Example:

```text
review-classification-v1.0
review-classification-v1.1
review-classification-v2.0
```

Document:

* Changes
* Motivation
* Performance impact
* Evaluation results

Never overwrite prompts without history.

---

# Retry Strategy

AI outputs may fail.

Handle:

* Invalid JSON
* Missing fields
* Empty responses
* Hallucinated fields
* Schema violations

Retry intelligently.

Do not repeatedly submit identical prompts without diagnosing failures.

---

# Prompt Validation

Validate every response before downstream processing.

Check:

* JSON validity
* Required fields
* Confidence present
* Enum values
* Schema compliance
* Null handling

Invalid outputs should never silently propagate.

---

# Hallucination Guardrails

Reduce hallucinations by:

* Constraining outputs.
* Defining allowed labels.
* Providing taxonomies.
* Requiring evidence.
* Rejecting unsupported claims.
* Returning "Unknown" instead of guessing.

Prefer abstention over fabrication.

---

# Prompt Evaluation

Evaluate prompts using representative datasets.

Measure:

* Accuracy
* Precision
* Recall
* Consistency
* Stability
* Hallucination Rate
* Cost
* Latency
* Human Agreement

Prompt quality should be measurable.

---

# Prompt Observability

Track prompt performance.

Capture:

* Prompt version
* Model version
* Input size
* Output size
* Latency
* Token usage
* Success rate
* Failure reason

Treat prompts as observable production components.

---

# Prompt Reusability

Avoid embedding business logic directly into prompts.

Instead:

* Pass taxonomies as inputs.
* Pass schemas as inputs.
* Pass business objectives as inputs.

Prompts should remain reusable across domains.

---

# Multi-Prompt Orchestration

Prefer orchestration over monolithic prompting.

Example workflow:

```text
Review
      ↓
Normalizer
      ↓
Complaint Extractor
      ↓
Classifier
      ↓
JTBD Inference
      ↓
Root Cause Analysis
      ↓
Cluster Builder
      ↓
Insight Generator
      ↓
Opportunity Ranker
```

Each component should be independently testable.

---

# Prompt Review Checklist

Before deploying a prompt verify:

* One clear objective
* Structured inputs
* Structured outputs
* Defined schema
* Validation rules
* Confidence reporting
* Evidence requirements
* Version assigned
* Evaluation completed
* Documentation updated

---

# Common Anti-Patterns

Avoid:

* Giant "do everything" prompts.
* Hidden assumptions.
* Free-form JSON.
* Unbounded outputs.
* Prompt duplication.
* Hardcoded business rules.
* Missing validation.
* Ignoring low-confidence outputs.
* Prompt changes without regression testing.

---

# Definition of Done

A production prompt is complete only when:

* It solves one reasoning task.
* Inputs and outputs are fully specified.
* Output schema is validated.
* Evidence is preserved.
* Confidence is reported.
* Evaluation metrics meet project thresholds.
* Prompt version is recorded.
* Documentation is updated.
* Regression tests pass.
* The prompt can be reused across workflows.

---

# Guiding Principle

> **A prompt is not an instruction. A prompt is a software component. Design it with the same discipline as production code: modular, testable, observable, versioned, and continuously improved.**
