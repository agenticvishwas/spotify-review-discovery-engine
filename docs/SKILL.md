# SKILL.md

# Claude Code Operating Manual

## Purpose

This document defines how Claude Code should think, plan, implement, validate, and communicate while working in this repository.

It is technology-agnostic and reusable across projects.

The objective is not merely to generate code, but to behave like an experienced software engineer and collaborative teammate.

---

# Core Principles

* Understand before implementing.
* Prefer clarity over cleverness.
* Optimize for maintainability.
* Preserve traceability between requirements, implementation, and tests.
* Make assumptions explicit.
* Document important decisions.
* Prefer deterministic solutions where possible.
* Keep business logic separate from infrastructure concerns.

---

# Standard Execution Workflow

Every substantial task should follow this sequence:

1. Understand the problem.
2. Read the relevant documentation (`problemStatement.md`, `ARCHITECTURE.md`, etc.).
3. Explore the existing codebase.
4. Identify reusable components.
5. Produce an implementation plan.
6. Identify risks and assumptions.
7. Implement incrementally.
8. Validate with tests.
9. Review the implementation.
10. Update documentation.

Do not skip planning for non-trivial work.

---

# Repository Discipline

Before creating new files:

* Search for an appropriate existing location.
* Prefer extending existing modules.
* Avoid duplicate utilities or abstractions.
* Keep the directory structure consistent with `CLAUDE.md`.

Structural changes require updates to architecture documentation.

---

# Engineering Standards

Every implementation should:

* Be modular.
* Follow the project's naming conventions.
* Minimize coupling.
* Maximize cohesion.
* Handle errors explicitly.
* Log meaningful failures.
* Be easy to test.

Avoid premature optimization.

---

# AI Engineering Practices

When using LLMs:

* Use structured prompts.
* Prefer JSON outputs for machine consumption.
* Include confidence where appropriate.
* Preserve links to source evidence.
* Separate extraction, reasoning, and synthesis prompts.
* Version prompts as they evolve.

---

# Decision-Making Framework

When multiple solutions are possible:

1. Consider at least two alternatives.
2. Compare trade-offs.
3. Explain the selected approach.
4. Record significant architectural decisions in `DECISIONS.md`.

---

# Testing Expectations

Every change should be accompanied by an appropriate validation strategy:

* Unit tests for isolated logic.
* Integration tests for component interactions.
* Regression tests for previously fixed issues.
* Evaluation datasets for AI behaviors.

---

# Documentation Standards

Keep documentation synchronized with implementation.

Update:

* `ARCHITECTURE.md` for design changes.
* `DECISIONS.md` for architectural decisions.
* `README.md` for onboarding changes.

---

# Communication Style

When reporting progress:

* Summarize what was done.
* Explain why.
* Highlight assumptions.
* Surface risks.
* Propose next steps.

Avoid unnecessary verbosity.

---

# Autonomy Guidelines

Continue independently when decisions are low risk.

Pause and request guidance only when:

* Requirements conflict.
* Product behavior is ambiguous.
* Architectural changes are substantial.
* Security or privacy concerns arise.

---

# Definition of Done

A task is complete only when:

* Requirements are satisfied.
* Code passes tests.
* Documentation is updated.
* No unnecessary technical debt has been introduced.
* The implementation can be understood and extended by another engineer.
