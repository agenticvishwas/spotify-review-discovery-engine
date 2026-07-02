"""Tests for QueryPlanner — verifies correct query steps are generated per intent."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from query_engine.intent_classifier import ClassifiedIntent, QueryIntent
from query_engine.query_planner import QueryPlanner


@pytest.fixture
def planner():
    return QueryPlanner()


def _classified(intent: QueryIntent, entity=None) -> ClassifiedIntent:
    return ClassifiedIntent(intent=intent, confidence=0.9, extracted_entity=entity)


def test_discovery_friction_plan(planner):
    plan = planner.build(_classified(QueryIntent.DISCOVERY_FRICTION), "")
    tables = [s.table for s in plan.steps]
    assert "analyzed_reviews" in tables
    assert "clusters" in tables
    assert "insights" in tables


def test_opportunity_list_plan(planner):
    plan = planner.build(_classified(QueryIntent.OPPORTUNITY_LIST), "")
    assert len(plan.steps) == 1
    assert plan.steps[0].table == "insights"
    assert plan.steps[0].filters.get("review_required") == 0


def test_jtbd_plan(planner):
    plan = planner.build(_classified(QueryIntent.JTBD_LOOKUP), "")
    assert plan.steps[0].table == "jtbd_profiles"
    assert plan.steps[0].order_by == "gap_score DESC"


def test_segment_plan_uses_entity(planner):
    plan = planner.build(_classified(QueryIntent.SEGMENT_PROBLEMS, entity="power_user"), "")
    assert plan.steps[0].filters.get("user_segment_signal") == "power_user"


def test_segment_plan_defaults_power_user(planner):
    plan = planner.build(_classified(QueryIntent.SEGMENT_PROBLEMS, entity=None), "")
    assert plan.steps[0].filters.get("user_segment_signal") == "power_user"


def test_trend_plan(planner):
    plan = planner.build(_classified(QueryIntent.TREND_QUERY), "")
    tables = [s.table for s in plan.steps]
    assert "clusters" in tables


def test_evidence_retrieval_uses_vector_search(planner):
    plan = planner.build(_classified(QueryIntent.EVIDENCE_RETRIEVAL), "my question")
    assert any(s.kind == "vector_search" for s in plan.steps)


def test_general_falls_back_to_insights(planner):
    plan = planner.build(_classified(QueryIntent.GENERAL), "something random")
    assert plan.steps[0].table == "insights"


def test_all_steps_have_limits(planner):
    for intent in QueryIntent:
        plan = planner.build(_classified(intent), "test")
        for step in plan.steps:
            assert step.limit > 0
