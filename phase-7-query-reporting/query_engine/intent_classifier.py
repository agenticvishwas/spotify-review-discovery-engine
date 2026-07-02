from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class QueryIntent(str, Enum):
    DISCOVERY_FRICTION = "discovery_friction"
    FEATURE_PROBLEMS = "feature_problems"
    SEGMENT_PROBLEMS = "segment_problems"
    JTBD_LOOKUP = "jtbd_lookup"
    OPPORTUNITY_LIST = "opportunity_list"
    TREND_QUERY = "trend_query"
    EVIDENCE_RETRIEVAL = "evidence_retrieval"
    GENERAL = "general"


@dataclass
class ClassifiedIntent:
    intent: QueryIntent
    confidence: float
    extracted_entity: Optional[str] = None  # feature name or segment name


_KEYWORD_RULES: list[tuple[QueryIntent, list[str]]] = [
    (QueryIntent.DISCOVERY_FRICTION, [
        "discover new music", "find new music", "discovery algorithm",
        "music discovery", "discovery broken", "discovery friction",
        "repetitive", "same songs", "same content", "same music",
        "algorithm repetitive", "no variety", "always the same",
        "recommend new", "serendipity", "stumble upon music",
    ]),
    (QueryIntent.JTBD_LOOKUP, [
        "job to be done", "jobs to be done", "jtbd",
        "trying to accomplish", "user goals", "user motivations",
        "jobs users", "what jobs", "user intent",
    ]),
    (QueryIntent.OPPORTUNITY_LIST, [
        "opportunity", "opportunities", "highest potential", "priority",
        "what should we build", "what to prioritize", "roadmap",
        "most impactful", "top opportunities", "biggest opportunities",
    ]),
    (QueryIntent.TREND_QUERY, [
        "getting worse", "worsening", "over time", "trend over",
        "increasing over", "problems increasing", "declining",
        "improving over time", "what problems are growing",
    ]),
    (QueryIntent.SEGMENT_PROBLEMS, [
        "power user", "casual user", "new user", "churned user",
        "user segment", "which segment", "type of user",
    ]),
    (QueryIntent.EVIDENCE_RETRIEVAL, [
        "show me reviews", "show me verbatims", "quote reviews",
        "actual reviews", "raw customer feedback", "customer quotes",
        "verbatim reviews",
    ]),
    (QueryIntent.FEATURE_PROBLEMS, [
        "daily mix", "discover weekly", "home screen", "podcast feature",
        "shuffle feature", "like button", "offline mode", "lyrics feature",
        "playlist feature", "radio feature", "library feature",
        "search feature", "queue feature", "download feature",
    ]),
]

_SEGMENT_MAP = {
    "power user": "power_user",
    "power_user": "power_user",
    "casual": "casual",
    "new user": "new",
    "new": "new",
    "churned": "churned",
}

_FEATURE_NAMES = [
    "discover weekly", "daily mix", "home screen", "radio", "search",
    "playlist", "podcast", "shuffle", "download", "lyrics", "queue",
    "library", "offline",
]


class IntentClassifier:
    def classify(self, question: str) -> ClassifiedIntent:
        q = question.lower()
        scores: dict[QueryIntent, int] = {i: 0 for i in QueryIntent}

        for intent, keywords in _KEYWORD_RULES:
            for kw in keywords:
                if kw in q:
                    # Longer phrase matches score proportionally more, so
                    # "discover weekly" (2 words) beats "discover" (1 word)
                    scores[intent] += len(kw.split())

        best = max(scores, key=lambda i: scores[i])
        best_score = scores[best]

        if best_score == 0:
            return ClassifiedIntent(intent=QueryIntent.GENERAL, confidence=0.5)

        total = sum(scores.values())
        confidence = min(0.95, best_score / max(total, 1) + 0.3)

        return ClassifiedIntent(
            intent=best,
            confidence=confidence,
            extracted_entity=self._extract_entity(q, best),
        )

    def _extract_entity(self, q: str, intent: QueryIntent) -> Optional[str]:
        if intent == QueryIntent.SEGMENT_PROBLEMS:
            for phrase, canonical in _SEGMENT_MAP.items():
                if phrase in q:
                    return canonical
        if intent == QueryIntent.FEATURE_PROBLEMS:
            for fn in _FEATURE_NAMES:
                if fn in q:
                    return fn
        return None
