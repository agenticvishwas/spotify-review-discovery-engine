"""Tests for report generators — uses an in-memory SQLite DB."""
import json
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from reports.opportunity_list import generate_json as opp_json, generate_csv as opp_csv
from reports.jtbd_report import generate_markdown as jtbd_md, generate_json as jtbd_json
from reports.executive_summary import generate as exec_summary


# ── Fixture: minimal in-memory DB ─────────────────────────────────────────────

@pytest.fixture
def conn():
    schema_path = (
        Path(__file__).parent.parent.parent / "phase-6-storage" / "schemas" / "001_initial.sql"
    )
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    if schema_path.exists():
        c.executescript(schema_path.read_text(encoding="utf-8"))
    else:
        # Minimal schema fallback for CI without phase-6
        c.executescript("""
            CREATE TABLE IF NOT EXISTS insights (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL,
                insight_type TEXT NOT NULL, affected_segment TEXT,
                frequency_score REAL, severity_score REAL, opportunity_score REAL,
                confidence TEXT NOT NULL DEFAULT 'medium',
                confidence_score REAL DEFAULT 0.0,
                reasoning TEXT, discovery_friction_related INTEGER DEFAULT 0,
                trend_direction TEXT, review_required INTEGER DEFAULT 0,
                generated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS insight_reviews (
                insight_id TEXT, review_id TEXT, verbatim TEXT,
                PRIMARY KEY (insight_id, review_id)
            );
            CREATE TABLE IF NOT EXISTS insight_clusters (
                insight_id TEXT, cluster_id TEXT,
                PRIMARY KEY (insight_id, cluster_id)
            );
            CREATE TABLE IF NOT EXISTS jtbd_profiles (
                id TEXT PRIMARY KEY, job_statement TEXT NOT NULL,
                short_label TEXT NOT NULL, satisfaction_score REAL,
                gap_score REAL, frequency_estimate INTEGER,
                user_segments TEXT, gap_description TEXT,
                generated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS normalized_reviews (
                id TEXT PRIMARY KEY, source_review_id TEXT,
                clean_text TEXT NOT NULL, platform TEXT NOT NULL,
                published_at TEXT, normalized_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS clusters (
                id TEXT PRIMARY KEY, label TEXT NOT NULL, theme TEXT NOT NULL,
                is_discovery_related INTEGER DEFAULT 0, size INTEGER DEFAULT 0,
                discovery_friction_rate REAL, is_micro_cluster INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS pipeline_runs (
                id TEXT PRIMARY KEY, started_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'running', completed_at TEXT
            );
            CREATE TABLE IF NOT EXISTS analyzed_reviews (
                id TEXT PRIMARY KEY, normalized_review_id TEXT,
                discovery_friction_detected INTEGER DEFAULT 0,
                analysis_status TEXT DEFAULT 'success', confidence_score REAL DEFAULT 0
            );
        """)
    c.commit()

    now = datetime.now(timezone.utc).isoformat()
    insight_id = str(uuid.uuid4())
    c.execute(
        """INSERT INTO insights
           (id, title, description, insight_type, affected_segment,
            frequency_score, severity_score, opportunity_score,
            confidence, confidence_score, reasoning,
            discovery_friction_related, trend_direction, review_required, generated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (insight_id, "Better Discovery UX", "Users want more serendipitous discovery.",
         "opportunity", "casual", 0.6, 0.5, 0.72, "high", 0.82,
         "Cluster evidence supports this.", 1, "increasing", 0, now),
    )
    c.execute(
        "INSERT INTO insight_reviews (insight_id, review_id, verbatim) VALUES (?,?,?)",
        (insight_id, str(uuid.uuid4()), "I always hear the same songs."),
    )
    jtbd_id = str(uuid.uuid4())
    c.execute(
        """INSERT INTO jtbd_profiles
           (id, job_statement, short_label, satisfaction_score, gap_score,
            frequency_estimate, user_segments, gap_description, generated_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (jtbd_id, "Discover music I've never heard before", "Novel Discovery",
         0.4, 0.6, 500, "casual,new", "Users want serendipity but get repetition.", now),
    )
    c.commit()
    return c


# ── Opportunity list ──────────────────────────────────────────────────────────

def test_opp_json_returns_valid_json(conn):
    out = opp_json(conn)
    data = json.loads(out)
    assert "opportunities" in data
    assert len(data["opportunities"]) == 1
    assert data["opportunities"][0]["title"] == "Better Discovery UX"


def test_opp_json_includes_verbatims(conn):
    out = opp_json(conn)
    data = json.loads(out)
    assert "supporting_verbatims" in data["opportunities"][0]
    assert "I always hear the same songs." in data["opportunities"][0]["supporting_verbatims"]


def test_opp_csv_has_header(conn):
    out = opp_csv(conn)
    assert "title" in out.splitlines()[0]
    assert "Better Discovery UX" in out


# ── JTBD report ───────────────────────────────────────────────────────────────

def test_jtbd_markdown_renders(conn):
    out = jtbd_md(conn)
    assert "# Jobs-to-Be-Done Report" in out
    assert "Novel Discovery" in out
    assert "0.60" in out  # gap score


def test_jtbd_json_returns_profiles(conn):
    out = jtbd_json(conn)
    data = json.loads(out)
    assert data["total"] == 1
    assert data["jtbd_profiles"][0]["short_label"] == "Novel Discovery"


# ── Executive summary ─────────────────────────────────────────────────────────

def test_executive_summary_renders(conn):
    out = exec_summary(conn, top_n=5)
    assert "# Spotify Discovery Intelligence" in out
    assert "Better Discovery UX" in out
    # JTBD table renders job_statement (full text), not short_label
    assert "Discover music I've never heard before" in out
