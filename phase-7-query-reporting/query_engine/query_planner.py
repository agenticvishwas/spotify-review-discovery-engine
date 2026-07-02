from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional
from .intent_classifier import ClassifiedIntent, QueryIntent


@dataclass
class QueryStep:
    kind: str  # "sql" | "vector_search"
    table: Optional[str] = None
    filters: dict[str, Any] = field(default_factory=dict)
    order_by: Optional[str] = None
    limit: int = 50
    description: str = ""


@dataclass
class QueryPlan:
    intent: QueryIntent
    steps: list[QueryStep] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)


class QueryPlanner:
    def build(self, classified: ClassifiedIntent, raw_question: str) -> QueryPlan:
        intent = classified.intent
        entity = classified.extracted_entity

        if intent == QueryIntent.DISCOVERY_FRICTION:
            return QueryPlan(
                intent=intent,
                steps=[
                    QueryStep(
                        kind="sql", table="analyzed_reviews",
                        filters={"discovery_friction_detected": 1, "min_confidence": 0.5},
                        order_by="confidence_score DESC", limit=100,
                        description="Reviews with discovery friction",
                    ),
                    QueryStep(
                        kind="sql", table="clusters",
                        filters={"is_discovery_related": 1, "is_micro_cluster": 0},
                        order_by="discovery_friction_rate DESC", limit=10,
                        description="Discovery-related clusters",
                    ),
                    QueryStep(
                        kind="sql", table="insights",
                        filters={"discovery_friction_related": 1, "review_required": 0},
                        order_by="opportunity_score DESC", limit=10,
                        description="Discovery-related insights",
                    ),
                ],
                context={"focus": "discovery_friction"},
            )

        elif intent == QueryIntent.FEATURE_PROBLEMS:
            return QueryPlan(
                intent=intent,
                steps=[
                    QueryStep(
                        kind="sql", table="analyzed_reviews",
                        filters={"feature_mention": entity},
                        order_by="sentiment_score ASC", limit=50,
                        description=f"Reviews mentioning: {entity}",
                    ),
                    QueryStep(
                        kind="sql", table="insights",
                        filters={"review_required": 0},
                        order_by="opportunity_score DESC", limit=5,
                        description="Top insights",
                    ),
                ],
                context={"feature": entity},
            )

        elif intent == QueryIntent.SEGMENT_PROBLEMS:
            segment = entity or "power_user"
            return QueryPlan(
                intent=intent,
                steps=[
                    QueryStep(
                        kind="sql", table="analyzed_reviews",
                        filters={"user_segment_signal": segment},
                        order_by="confidence_score DESC", limit=50,
                        description=f"Reviews from segment: {segment}",
                    ),
                    QueryStep(
                        kind="sql", table="user_segments",
                        filters={"segment_label": segment},
                        limit=1,
                        description="Segment profile",
                    ),
                ],
                context={"segment": segment},
            )

        elif intent == QueryIntent.JTBD_LOOKUP:
            return QueryPlan(
                intent=intent,
                steps=[
                    QueryStep(
                        kind="sql", table="jtbd_profiles",
                        filters={}, order_by="gap_score DESC", limit=20,
                        description="All JTBD profiles by gap score",
                    ),
                ],
                context={},
            )

        elif intent == QueryIntent.OPPORTUNITY_LIST:
            return QueryPlan(
                intent=intent,
                steps=[
                    QueryStep(
                        kind="sql", table="insights",
                        filters={"review_required": 0},
                        order_by="opportunity_score DESC", limit=20,
                        description="Top opportunities ranked by score",
                    ),
                ],
                context={},
            )

        elif intent == QueryIntent.TREND_QUERY:
            return QueryPlan(
                intent=intent,
                steps=[
                    QueryStep(
                        kind="sql", table="clusters",
                        filters={"trend_direction": "increasing", "is_micro_cluster": 0},
                        order_by="size DESC", limit=10,
                        description="Clusters with increasing trend",
                    ),
                    QueryStep(
                        kind="sql", table="insights",
                        filters={"trend_direction": "increasing"},
                        order_by="severity_score DESC", limit=10,
                        description="Insights with worsening trend",
                    ),
                ],
                context={},
            )

        elif intent == QueryIntent.EVIDENCE_RETRIEVAL:
            return QueryPlan(
                intent=intent,
                steps=[
                    QueryStep(
                        kind="vector_search",
                        description="Semantic search for relevant reviews",
                        limit=10,
                    ),
                ],
                context={"question": raw_question},
            )

        else:  # GENERAL fallback
            return QueryPlan(
                intent=intent,
                steps=[
                    QueryStep(
                        kind="sql", table="insights",
                        filters={"review_required": 0},
                        order_by="opportunity_score DESC", limit=10,
                        description="Top insights (general fallback)",
                    ),
                ],
                context={"question": raw_question},
            )
