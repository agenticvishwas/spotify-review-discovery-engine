"""Phase 7 — Query & Reporting Dashboard (Home / Overview)

Launch via:  python run_dashboard.py
             streamlit run dashboards/app.py
"""
from __future__ import annotations
import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pandas as pd
import streamlit as st

from dashboards.db import fetch_overview_stats

st.set_page_config(
    page_title="Spotify Review Intelligence",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("Spotify Review Discovery Engine")
st.caption("Voice of Customer — AI-powered product intelligence for PMs")

# ── Data freshness check ──────────────────────────────────────────────────────
stats = fetch_overview_stats()

last_run = stats.get("last_successful_run")
if last_run is None:
    st.warning(
        "No completed pipeline runs found. Run Phases 1–6 to populate the knowledge base."
    )
else:
    from datetime import datetime, timezone
    try:
        last_dt = datetime.fromisoformat(last_run.replace("Z", "+00:00"))
        age_h = (datetime.now(timezone.utc) - last_dt).total_seconds() / 3600
        if age_h > 48:
            st.error(
                f"Data Stale — last successful run was {int(age_h)}h ago. Re-run the pipeline."
            )
        else:
            st.success(f"Data fresh — last pipeline run: {last_run[:19]} UTC")
    except Exception:
        st.info(f"Last pipeline run: {last_run}")

st.divider()

# ── KPI row ───────────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("Reviews Analyzed", f"{stats['total_reviews']:,}")
c2.metric("Discovery Friction Rate", f"{stats['friction_rate']}%")
c3.metric("Product Insights (ready)", stats["total_insights"])
c4.metric("Theme Clusters", stats["total_clusters"])

st.divider()

# ── Charts ────────────────────────────────────────────────────────────────────
col_l, col_r = st.columns(2)

with col_l:
    st.subheader("Reviews by Platform")
    if stats["by_platform"]:
        df = pd.DataFrame(
            list(stats["by_platform"].items()), columns=["Platform", "Count"]
        ).sort_values("Count", ascending=False)
        st.bar_chart(df.set_index("Platform"))
    else:
        st.info("No reviews ingested yet.")

with col_r:
    st.subheader("Sentiment Distribution")
    if stats["by_sentiment"]:
        order = ["positive", "neutral", "mixed", "negative"]
        df = pd.DataFrame(
            [(k, v) for k, v in stats["by_sentiment"].items()],
            columns=["Sentiment", "Count"],
        )
        df["Sentiment"] = pd.Categorical(df["Sentiment"], categories=order, ordered=True)
        df = df.sort_values("Sentiment")
        st.bar_chart(df.set_index("Sentiment"))
    else:
        st.info("No analyzed reviews yet.")

st.divider()
st.caption(
    "Use the sidebar to navigate to Discovery Insights, JTBD Map, Opportunity List, "
    "Segment Explorer, NL Query, or Evidence Viewer."
)
