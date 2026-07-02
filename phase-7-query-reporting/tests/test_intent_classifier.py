"""Tests for IntentClassifier — verifies keyword routing for all intent types."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from query_engine.intent_classifier import IntentClassifier, QueryIntent


@pytest.fixture
def clf():
    return IntentClassifier()


def test_discovery_friction_intent(clf):
    result = clf.classify("Music discovery is repetitive — why is the algorithm showing same songs?")
    assert result.intent == QueryIntent.DISCOVERY_FRICTION
    assert result.confidence > 0.5


def test_opportunity_list_intent(clf):
    result = clf.classify("What are the top opportunities ranked by potential?")
    assert result.intent == QueryIntent.OPPORTUNITY_LIST


def test_jtbd_intent(clf):
    result = clf.classify("What jobs to be done are users trying to accomplish?")
    assert result.intent == QueryIntent.JTBD_LOOKUP


def test_segment_intent_extracts_entity(clf):
    result = clf.classify("What does the power user segment complain about most?")
    assert result.intent == QueryIntent.SEGMENT_PROBLEMS
    assert result.extracted_entity == "power_user"


def test_trend_intent(clf):
    result = clf.classify("Which problems are getting worse over time?")
    assert result.intent == QueryIntent.TREND_QUERY


def test_feature_intent_extracts_entity(clf):
    result = clf.classify("What are the main issues users have with the Discover Weekly feature?")
    assert result.intent == QueryIntent.FEATURE_PROBLEMS
    assert result.extracted_entity == "discover weekly"


def test_evidence_retrieval_intent(clf):
    result = clf.classify("Show me verbatim reviews about music recommendations")
    assert result.intent == QueryIntent.EVIDENCE_RETRIEVAL


def test_general_fallback(clf):
    result = clf.classify("hello")
    assert result.intent == QueryIntent.GENERAL


def test_confidence_is_bounded(clf):
    result = clf.classify("discover new music discovery recommendation explore")
    assert 0.0 <= result.confidence <= 1.0
