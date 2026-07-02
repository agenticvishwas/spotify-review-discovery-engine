from __future__ import annotations
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_SYSTEM = """\
You are an internal AI research assistant for a Product Manager at Spotify.
Answer questions about customer feedback using only the provided evidence.
Never speculate beyond what the data shows. Return valid JSON only — no markdown fences."""

_PROMPT = """\
The PM asked: "{question}"

Relevant insights from the knowledge base:
{insights_json}

Supporting customer verbatims:
{evidence_json}

Answer concisely and accurately.
- Reference specific evidence; quote reviews where helpful
- State confidence based on evidence volume and consistency
- Highlight caveats if data is sparse or ambiguous
- Do not speculate beyond what the evidence supports

Return ONLY this JSON:
{{
  "answer": "prose answer (2-4 paragraphs)",
  "confidence": "high|medium|low",
  "key_findings": [
    {{
      "finding": "concise finding",
      "evidence_count": 0,
      "verbatims": ["quote1", "quote2"]
    }}
  ],
  "caveats": "string or null"
}}"""


class AnswerSynthesizer:
    def __init__(self, llm_provider: Any):
        self._llm = llm_provider

    def synthesize(
        self,
        question: str,
        query_results: dict[str, Any],
        verbatims: list[dict],
        max_insights: int = 10,
    ) -> dict[str, Any]:
        insights = self._extract_insights(query_results, max_insights)
        evidence = self._format_verbatims(verbatims[:10])

        prompt = _PROMPT.format(
            question=question,
            insights_json=json.dumps(insights, indent=2, default=str)[:3000],
            evidence_json=json.dumps(evidence, indent=2, default=str)[:2000],
        )

        try:
            raw = self._llm.complete(prompt, system=_SYSTEM, max_tokens=1024)
            parsed = self._parse(raw)
        except Exception as exc:
            logger.error("answer_synthesis_failed error=%s", exc)
            parsed = {
                "answer": "Unable to synthesize an answer from the available data.",
                "confidence": "low",
                "key_findings": [],
                "caveats": f"LLM error: {exc}",
            }

        parsed["question"] = question
        parsed["generated_at"] = datetime.now(timezone.utc).isoformat()
        parsed["related_insights"] = [
            row.get("id") for step in query_results.get("steps", [])
            for row in step.get("rows", [])
            if row.get("id") and step.get("table") == "insights"
        ][:5]
        return parsed

    def _extract_insights(self, results: dict, max_count: int) -> list[dict]:
        out: list[dict] = []
        keep = ("id", "title", "description", "confidence_score", "insight_type", "opportunity_score")
        for step in results.get("steps", []):
            for row in step.get("rows", []):
                out.append({k: row[k] for k in keep if k in row})
                if len(out) >= max_count:
                    return out
        return out

    def _format_verbatims(self, verbatims: list[dict]) -> list[dict]:
        return [
            {
                "text": v.get("verbatim", ""),
                "platform": v.get("platform", ""),
                "rating": v.get("normalized_rating"),
                "date": (v.get("published_at") or "")[:10],
            }
            for v in verbatims
            if v.get("verbatim")
        ]

    def _parse(self, text: str) -> dict:
        text = text.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        return json.loads(text)
