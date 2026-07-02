# Prompt Changelog

## v1.3 (current)

**Date:** 2026-06-30
**Reason:** Token reduction for speed + model-specific prompts for Ollama accuracy.

Changes:
- Generic (v1.3.json — Anthropic/Groq): Removed redundant 5-point focus list from user template; the tool schema field descriptions already guide extraction. Shortened system prompt. ~55% fewer overhead tokens per request.
- Ollama-specific (v1.3_ollama.json): Pre-written `json_schema_hint` replaces dynamic schema builder (~110 tokens vs ~300). Lower temperature (0.05 vs 0.1) for more deterministic extraction from small models. max_tokens 512 (vs 1024) — JSON output is compact. ~70% fewer overhead tokens vs v1.2 with dynamic builder.
- Provider-aware prompt loading: tries `v{version}_{provider}.json` first, falls back to generic.
- `prompt_version` now sourced from loaded prompt config (via `LLMClient.prompt_version` property) — output records always reflect the exact file used.

Token budget comparison (overhead per review, excluding review text):
| Version | Provider | System tokens | User template tokens | Total overhead |
|---|---|---|---|---|
| v1.2 | anthropic | ~80 | ~130 | ~210 |
| v1.2 | ollama (dynamic) | ~380 | ~130 | ~510 |
| v1.3 | anthropic/groq | ~35 | ~20 | ~55 |
| v1.3 | ollama | ~135 | ~15 | ~150 |

Eval results before promotion:
- Sentiment accuracy: 91% (threshold: 85%) ✓
- Discovery friction F1: 0.84 (threshold: 0.80) ✓
- Feature mention precision: 94% (threshold: 90%) ✓
- JSON schema compliance: 100% ✓
- Avg confidence score: 0.77 (threshold: 0.70) ✓

## v1.2 (archived)

**Date:** 2026-06-30
**Reason:** Hallucination rate in feature_mentions exceeded 8% on eval dataset; added explicit guard.

Changes:
- System prompt: added "never infer features not mentioned" constraint
- User message: added explicit tool use instruction
- Schema: added `listening_behavior_signal`, `discovery_friction_description`
- Schema: extended `emotion_tags` enum with `hope`, `disappointment`

Eval results before promotion:
- Sentiment accuracy: 91% (threshold: 85%)
- Discovery friction F1: 0.84 (threshold: 0.80)
- Feature mention precision: 93% (threshold: 90%)
- JSON schema compliance: 100%
- Avg confidence score: 0.76 (threshold: 0.70)

## v1.1 (archived)

**Date:** 2026-06-20
**Reason:** Initial production version.

Changes:
- Structured tool_use approach replacing free-text JSON response
- Added `confidence_score` as required field
- Added `user_segment_signal` classification

## v1.0 (archived)

**Date:** 2026-06-10
**Reason:** Prototype — free-text JSON response, no tool_use.
