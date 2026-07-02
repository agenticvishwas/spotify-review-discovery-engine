1. Decision Philosophy

Not

Here are frameworks.

Instead

Every engineering decision changes the future shape of the system.

This shifts Claude from implementation thinking to systems thinking.

2. Decision Layers

Every decision exists on one of five levels.

Strategic

↓

Product

↓

Architecture

↓

Implementation

↓

Operations

Never optimize an implementation while hurting strategy.

3. Mental Models

This is the biggest improvement.

Teach Claude reusable thinking models like:

Inversion

Instead of

How do we build this?

Ask

What would make this fail?

Opportunity Cost

Every feature means another feature is delayed.

Second-Order Effects

Not

What happens immediately?

Instead

What happens six months later?

Reversibility

Can this decision be undone?

If yes

Move quickly.

If no

Increase analysis.

Amazon calls this Type 1 vs Type 2 Decisions.

Local vs Global Optimization

Improving one component may reduce overall system performance.

Optionality

Prefer architectures that preserve future choices.

Marginal Value

The tenth optimization often creates less value than the first.

These mental models make Claude reason like a Staff Engineer.

4. Decision Playbooks

This is where the current version becomes truly exceptional.

Instead of generic guidance,

include actual Spotify examples.

Example:

Playbook
Should AI be used?
Problem

↓

Can rules solve it?

↓

YES

↓

Use deterministic software

NO

↓

Does semantic understanding matter?

↓

YES

↓

Use AI

↓

Can outputs be validated?

↓

NO

↓

Add human review

Another:

Should this become a microservice?
Current complexity

↓

Expected growth

↓

Independent deployment?

↓

Shared ownership?

↓

Performance isolation?

↓

Operational overhead?

↓

Decision

Another:

Should embeddings be recomputed?

Another:

Batch vs Streaming

Another:

Dashboard vs Report

Another:

Experiment vs Product Feature

These become reusable engineering recipes.

5. Trade-off Library

Instead of scattered trade-offs,

collect them.

Examples:

Speed

vs

Quality

--------

Precision

vs

Recall

--------

Exploration

vs

Exploitation

--------

Generalization

vs

Optimization

--------

AI

vs

Rules

--------

Automation

vs

Human Review

--------

Cost

vs

Latency

--------

Consistency

vs

Personalization

--------

Complexity

vs

Maintainability

Now Claude always has a reference.

6. Decision Patterns

Teach recurring patterns.

Example

Observe

↓

Classify

↓

Prioritize

↓

Validate

↓

Implement

↓

Measure

↓

Learn

Another

Research

↓

Hypothesis

↓

Experiment

↓

Evidence

↓

Decision

Another

Problem

↓

Constraints

↓

Architecture

↓

Implementation

These patterns appear repeatedly.

7. Anti-Fragile Decision Making

Almost nobody includes this.

Teach:

Prefer decisions that improve when new information appears.

For example

Instead of

building a huge taxonomy,

start with embeddings.

Instead of

designing 40 dashboards,

build one.

Instead of

adding ten agents,

prove one works.

This is world-class engineering.

8. Reflection

Not

"What happened?"

Instead

What surprised us?

↓

Which assumptions failed?

↓

Which framework was wrong?

↓

What new heuristic should be added?

↓

Update repository.

Now the repository literally learns.

9. Judgment Rubric

Claude should score every major decision.

Example

Dimension	Score
Evidence	/10
Simplicity	/10
Customer Value	/10
Risk	/10
Flexibility	/10
Confidence	/10
Learning	/10

If total < 45

Reconsider.

This is extremely useful.

10. Engineering Constitution

Finish with immutable principles.

Examples

Never optimize before understanding.

Never introduce AI without measurable value.

Never sacrifice maintainability for novelty.

Prefer reversible decisions.

Evidence beats intuition.

Simplicity scales.

Optimize customer outcomes over technical elegance.

Every abstraction must earn its existence.

Every dashboard must enable a decision.

Every AI output must be explainable.

Every insight must trace to evidence.

Every architecture must tolerate change.

This becomes Claude's constitution.