# Documentation Skills

**Version:** 2.0 (Engineering Knowledge Operating System)

**Purpose**

Define how engineering knowledge should be created, maintained, versioned, and evolved so that every decision, architecture choice, AI workflow, and implementation remains understandable, reproducible, and maintainable.

Documentation is part of the product.

---

# Mission

Your responsibility is **not** to write documentation.

Your responsibility is to preserve engineering knowledge.

Every important decision should outlive the engineer who made it.

Documentation exists to reduce future uncertainty.

---

# Documentation Philosophy

Documentation is not a deliverable.

Documentation is infrastructure.

It should:

* Explain why
* Preserve context
* Capture decisions
* Enable onboarding
* Support maintenance
* Accelerate future development

If documentation cannot answer **"Why was this built this way?"**, it is incomplete.

---

# Documentation Hierarchy

Every repository should organize knowledge from strategy to implementation.

```text
Vision
      ↓
Problem Statement
      ↓
Product Strategy
      ↓
Architecture
      ↓
Decision Records
      ↓
Data Contracts
      ↓
AI Workflows
      ↓
Implementation
      ↓
Operations
      ↓
Lessons Learned
```

Never begin documentation with implementation.

---

# Documentation Principles

Every document should be:

* Purpose-driven
* Versioned
* Discoverable
* Cross-referenced
* Evidence-backed
* Continuously updated
* Actionable
* Concise without sacrificing clarity

Documentation should evolve alongside the codebase.

---

# Documentation Layers

## Layer 1 — Business Documentation

Capture:

* Vision
* Product goals
* Success metrics
* Customer problems
* JTBD
* Business constraints

Audience:

* Product Managers
* Stakeholders
* Executives

---

## Layer 2 — Product Documentation

Capture:

* User journeys
* Personas
* Opportunities
* Product requirements
* Experiments
* Prioritization rationale

Audience:

* Product
* Design
* Engineering

---

## Layer 3 — Architecture Documentation

Capture:

* System context
* Component diagrams
* Data flow
* AI workflow
* Service boundaries
* Design principles
* Technology choices

Audience:

* Engineers
* Architects

---

## Layer 4 — Engineering Documentation

Capture:

* Repository structure
* Build process
* APIs
* Schemas
* Prompt contracts
* Data contracts
* Testing strategy

Audience:

* Developers

---

## Layer 5 — Operational Documentation

Capture:

* Deployment
* Monitoring
* Troubleshooting
* Performance
* Incident response
* Maintenance

Audience:

* Operations
* Future maintainers

---

# Documentation Lifecycle

```text
Idea
      ↓
Decision
      ↓
Implementation
      ↓
Validation
      ↓
Release
      ↓
Reflection
      ↓
Knowledge Capture
```

Every major implementation should conclude with updated documentation.

---

# Repository Knowledge Map

Every repository should include:

```text
README.md

problemStatement.md

ARCHITECTURE.md

DECISIONS.md

ROADMAP.md

CHANGELOG.md

CONTRIBUTING.md

docs/
    product/
    architecture/
    ai/
    data/
    api/
    operations/
    research/
    evaluation/
```

Knowledge should be easy to locate.

---

# README Standard

Every README should answer:

1. What problem does this solve?
2. Why does it exist?
3. Who is it for?
4. How is it structured?
5. How do I run it?
6. How do I evaluate it?
7. Where can I learn more?

A README is an entry point—not a complete manual.

---

# Architecture Decision Records (ADRs)

Document every significant decision.

Each ADR should include:

* Decision title
* Date
* Status
* Context
* Alternatives considered
* Chosen solution
* Trade-offs
* Consequences
* Related documents

Record decisions while they are fresh.

---

# AI Documentation

Every AI capability should describe:

Purpose

↓

Inputs

↓

Prompt

↓

Model

↓

Output Schema

↓

Validation

↓

Evaluation Metrics

↓

Failure Modes

↓

Fallback Strategy

AI systems require explicit documentation because behavior is probabilistic.

---

# Prompt Documentation

For every production prompt record:

* Prompt ID
* Version
* Objective
* Input schema
* Output schema
* Dependencies
* Evaluation metrics
* Known limitations
* Change history

Treat prompts like APIs.

---

# Data Documentation

Every dataset should define:

* Source
* Schema
* Refresh cadence
* Quality metrics
* Lineage
* Privacy considerations
* Version
* Consumers

Data without documentation becomes unusable over time.

---

# API Documentation

Every API should specify:

* Endpoint
* Purpose
* Authentication
* Request schema
* Response schema
* Errors
* Examples
* Rate limits
* Version

Documentation should be executable where possible.

---

# Knowledge Traceability

Every document should link to related knowledge.

Example:

```text
Problem Statement
        ↓
Architecture
        ↓
ADR
        ↓
Implementation
        ↓
Tests
        ↓
Evaluation
```

Avoid isolated documents.

Build a connected knowledge graph.

---

# Living Documentation

Documentation should be updated whenever:

* Architecture changes
* Schemas change
* Prompts change
* Models change
* Product strategy changes
* Evaluation criteria change

Outdated documentation is worse than missing documentation.

---

# Documentation Quality Checklist

Before publishing verify:

✓ Purpose defined

✓ Audience identified

✓ Version updated

✓ Linked documents referenced

✓ Examples included

✓ Trade-offs documented

✓ Decisions explained

✓ Diagrams synchronized

✓ Terminology consistent

✓ Last reviewed date updated

---

# Common Anti-Patterns

Avoid:

* Documentation written only after implementation.
* Copying code into documents.
* Describing *what* without explaining *why*.
* Unversioned documents.
* Duplicate knowledge.
* Broken links.
* Architecture diagrams that don't match reality.
* README files that assume prior knowledge.
* Hidden engineering decisions.

---

# Documentation Review Process

Every major change should answer:

* Does this affect existing documentation?
* Which documents require updates?
* Has the architecture changed?
* Has the prompt contract changed?
* Has the data contract changed?
* Has the evaluation strategy changed?
* Have examples been updated?

Documentation reviews are part of code reviews.

---

# Documentation Metrics

Measure:

* Documentation coverage
* Broken link count
* Last updated age
* ADR completeness
* README completeness
* Schema documentation coverage
* Prompt documentation coverage
* Onboarding time

Knowledge quality is measurable.

---

# Definition of Done

Documentation is complete only when:

The business problem is clearly explained.

Architecture matches implementation.

Every significant decision is traceable.

AI workflows are documented.

Data contracts are defined.

Prompt contracts are versioned.

Evaluation strategy is reproducible.

Repository structure is understandable.

A new engineer can become productive without asking the original author for clarification.

---

# Documentation Maturity Model

```text
Level 1
Code Comments

↓

Level 2
Project Documentation

↓

Level 3
Engineering Documentation

↓

Level 4
Knowledge Management

↓

Level 5
Self-Documenting Engineering System
```

The objective is **Level 5**.

At Level 5:

* Every decision is preserved.
* Every document has a clear owner and lifecycle.
* Every artifact links to related knowledge.
* The repository explains itself.

---

# Guiding Principle

> **Documentation is not written for today's engineer. It is written for the engineer who joins six months from now, the product manager preparing the next roadmap, and the AI system that must reason consistently across evolving requirements. A great repository is not one with the most documents—it is one where every important decision, assumption, and workflow is easy to discover, understand, verify, and extend.**
