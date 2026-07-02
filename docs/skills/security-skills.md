# Security Skills

**Version:** 2.0 (AI Security Operating Manual)

**Purpose**

Define the security principles, engineering practices, and AI-specific safeguards required to build trustworthy, privacy-preserving, and resilient AI systems.

Security is not a feature.

Security is a property of the entire system.

This document governs how Claude designs, implements, validates, and maintains secure AI-powered engineering systems.

---

# Mission

Protect:

* Customer data
* Business data
* Credentials
* AI models
* Prompt assets
* Infrastructure
* Engineering knowledge

Every engineering decision should improve both functionality and security.

Security should be designed into the system—not added afterward.

---

# Security Philosophy

Security is everyone's responsibility.

It should be:

* Preventive
* Layered
* Observable
* Explainable
* Continuously validated

Assume:

* Credentials can leak.
* Inputs are untrusted.
* Models can hallucinate.
* Prompts can be manipulated.
* Dependencies can become vulnerable.

Design accordingly.

---

# Security Principles

Always:

Protect by default.

Minimize privilege.

Reduce attack surface.

Validate every input.

Encrypt sensitive data.

Preserve privacy.

Log responsibly.

Assume compromise.

Recover gracefully.

Security is continuous, not a milestone.

---

# Security Architecture

Every AI system should follow layered defense.

```text
User

↓

Public APIs

↓

Authentication

↓

Authorization

↓

Input Validation

↓

Review Ingestion

↓

PII Detection

↓

PII Redaction

↓

Normalized Dataset

↓

Embedding Pipeline

↓

LLM

↓

Insight Generation

↓

Dashboard

↓

Audit Logs
```

Every boundary should enforce security independently.

Never rely on a single control.

---

# Data Classification

Every dataset must be classified.

| Classification | Examples                     | Protection             |
| -------------- | ---------------------------- | ---------------------- |
| Public         | Public App Store reviews     | Integrity validation   |
| Internal       | Feature engineering datasets | Restricted access      |
| Confidential   | Internal analytics           | Role-based access      |
| Sensitive      | User identifiers, logs       | Encryption + masking   |
| Restricted     | API keys, credentials        | Secret management only |

Unknown data should be treated as Sensitive.

---

# Personally Identifiable Information (PII)

Public reviews may still contain personal information.

Detect:

* Email addresses
* Phone numbers
* Usernames
* Names (when appropriate)
* Physical addresses
* Payment references
* Device identifiers
* Social handles
* URLs containing personal information

Never expose PII to downstream dashboards unless explicitly required and authorized.

---

# Privacy-First Pipeline

Every review should pass through:

```text
Raw Review

↓

Language Detection

↓

PII Detection

↓

PII Redaction

↓

Spam Detection

↓

Safety Validation

↓

Normalization

↓

Embedding

↓

AI Analysis
```

LLMs should consume sanitized data whenever possible.

---

# Secrets Management

Never:

* Hardcode API keys.
* Commit credentials.
* Store secrets in source code.
* Print secrets to logs.
* Include secrets in prompts.

Always:

* Use environment variables.
* Use a secret manager in production.
* Rotate credentials regularly.
* Apply least privilege.
* Audit secret usage.

Secrets are infrastructure, not configuration.

---

# Authentication & Authorization

Every service should verify:

Who is making the request?

What are they allowed to access?

Should they access it now?

Prefer:

* Role-Based Access Control (RBAC)
* Principle of Least Privilege
* Short-lived credentials
* Token expiration
* Service-to-service authentication

Authentication identifies.

Authorization limits.

---

# Input Validation

Treat all external inputs as untrusted.

Validate:

* File formats
* Character encoding
* Payload size
* Schema compliance
* Unexpected fields
* Injection attempts
* Malformed content

Reject invalid input early.

---

# Prompt Security

Protect prompts as production assets.

Never:

* Reveal system prompts.
* Echo hidden instructions.
* Leak internal reasoning.
* Include secrets in prompts.
* Embed credentials.

Defend against:

* Prompt injection
* Context poisoning
* Jailbreak attempts
* Instruction override attacks
* Data exfiltration

Prompt security is application security.

---

# LLM Security

Before sending data to an LLM:

Verify:

* Data has been sanitized.
* PII has been removed or masked.
* Sensitive context is necessary.
* Output can be validated.

After receiving output:

Validate:

* Schema compliance
* Hallucination risk
* Confidence thresholds
* Evidence traceability

Never trust model output without verification.

---

# Embedding Security

Embeddings may encode sensitive information.

Protect:

* Embedding stores
* Vector databases
* Metadata
* Retrieval permissions

Never expose raw embeddings publicly.

Restrict retrieval based on authorization.

---

# Dashboard Security

Dashboards should display insights—not sensitive records.

Never expose:

* Email addresses
* Phone numbers
* Access tokens
* Internal IDs
* Secrets
* Raw credentials
* Debug logs

Prefer aggregation over individual records.

---

# Logging & Observability

Log enough to investigate issues.

Never log:

* Passwords
* API keys
* OAuth tokens
* Secrets
* PII
* Full prompts containing sensitive data

Log:

* Request IDs
* Timestamps
* Pipeline stages
* Errors
* Confidence scores
* Validation failures

Logs should support investigation without creating privacy risks.

---

# Dependency Security

Every dependency introduces risk.

Maintain:

* Dependency inventory
* Version pinning
* Vulnerability scanning
* Regular updates
* License review

Remove unused packages.

Smaller dependency graphs reduce attack surface.

---

# Secure AI Workflows

Every AI pipeline should include:

Input Validation

↓

Safety Checks

↓

PII Redaction

↓

Prompt Construction

↓

Model Invocation

↓

Output Validation

↓

Evidence Verification

↓

Confidence Estimation

↓

Audit Logging

Security should be integrated into every stage.

---

# Threat Modeling

Before implementation identify:

Assets

↓

Threat Actors

↓

Attack Surface

↓

Threat Scenarios

↓

Mitigations

↓

Residual Risk

Threat modeling should occur during design—not after deployment.

---

# AI Threats

Evaluate for:

* Prompt Injection
* Prompt Leakage
* Data Poisoning
* Hallucinations
* Retrieval Manipulation
* Training Data Leakage
* Prompt Extraction
* Model Abuse
* Output Manipulation

AI introduces new attack vectors beyond traditional software.

---

# Compliance Awareness

Design with awareness of:

* GDPR
* CCPA
* Platform Terms of Service
* Data Retention Policies
* User Deletion Requests

Legal compliance should influence architecture decisions.

---

# Data Retention

Define:

* Raw review retention
* Normalized dataset retention
* Embedding retention
* Log retention
* Audit retention

Delete data that no longer provides value.

Retain only what is necessary.

---

# Incident Response

Every system should prepare for failure.

Document:

* Detection
* Containment
* Investigation
* Recovery
* Root Cause Analysis
* Lessons Learned

Every incident should improve future resilience.

---

# Security Testing

Every release should include:

* Secret scanning
* Dependency vulnerability scanning
* Input validation testing
* Prompt injection testing
* PII leakage testing
* Authorization testing
* Authentication testing
* Rate limit testing
* Schema validation
* Adversarial AI testing

Security testing is continuous.

---

# Security Metrics

Track:

* Secrets exposed
* PII detection accuracy
* Prompt injection success rate
* Vulnerability count
* Dependency health
* Mean Time to Detect (MTTD)
* Mean Time to Respond (MTTR)
* Security regression rate

Measure security like any other engineering quality.

---

# Security Anti-Patterns

Avoid:

* Hardcoded credentials.
* Shared production accounts.
* Excessive permissions.
* Trusting AI outputs blindly.
* Logging sensitive information.
* Sending raw PII to models.
* Public vector databases.
* Ignoring dependency updates.
* Skipping threat modeling.
* Security reviews only before release.

Every shortcut creates future risk.

---

# Security Checklist

Before deployment verify:

✓ Secrets are managed securely.

✓ PII is detected and protected.

✓ Prompts contain no credentials.

✓ Inputs are validated.

✓ Outputs are verified.

✓ Dependencies are scanned.

✓ Authorization is enforced.

✓ Logs are sanitized.

✓ Threat model reviewed.

✓ Incident response documented.

---

# Definition of Done

Security is complete only when:

Customer data is protected.

Secrets are managed securely.

AI inputs are sanitized.

AI outputs are validated.

PII cannot leak through dashboards.

Threats have been modeled.

Security testing passes.

Access is least privilege.

Audit trails exist.

Security decisions are documented.

---

# Security Maturity Model

```text
Level 1
Reactive Security

↓

Level 2
Secure Development

↓

Level 3
Security by Design

↓

Level 4
AI Security Engineering

↓

Level 5
Zero Trust AI Platform
```

The objective is **Level 5**.

At Level 5:

* Security is integrated into every workflow.
* AI systems are explainable and resilient.
* Data privacy is enforced automatically.
* Secrets are never exposed.
* Every security decision is documented.
* Every release improves the security posture.

---

# Inheritance

This document inherits all principles from `ENGINEERING_PHILOSOPHY.md`.

If guidance conflicts, the Engineering Philosophy takes precedence.

---

# Guiding Principle

> **Security is not the absence of vulnerabilities—it is the presence of disciplined engineering practices that protect people, data, systems, and knowledge throughout the entire AI lifecycle. Every prompt, model invocation, dataset, dashboard, and deployment should assume untrusted inputs, minimize unnecessary exposure, preserve privacy by default, and remain transparent, auditable, and resilient. A secure AI system earns trust not through claims, but through architecture, evidence, and continuous verification.**
