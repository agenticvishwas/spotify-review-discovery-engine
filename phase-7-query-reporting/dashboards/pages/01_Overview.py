"""Page 1 — Overview: KPI summary and platform breakdown."""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboards.db import fetch_overview_stats, fetch_discovery_trend

st.set_page_config(page_title="Overview", layout="wide")
st.title("Overview")
st.caption("High-level health of the review knowledge base.")

stats = fetch_overview_stats()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Reviews", f"{stats['total_reviews']:,}")
c2.metric("Discovery Friction", f"{stats['friction_rate']}%")
c3.metric("Ready Insights", stats["total_insights"])
c4.metric("Theme Clusters", stats["total_clusters"])

st.divider()

# ── 90-day friction trend ─────────────────────────────────────────────────────
trend = fetch_discovery_trend()
if trend:
    df = pd.DataFrame(trend)
    df["friction_rate"] = df.apply(
        lambda r: round(r["friction"] / r["total"] * 100, 1) if r["total"] > 0 else 0,
        axis=1,
    )
    df["day"] = pd.to_datetime(df["day"])
    df = df.tail(90)

    st.subheader("Discovery Friction Rate — 90-day Trend")
    fig = px.line(df, x="day", y="friction_rate", labels={"friction_rate": "Friction %", "day": "Date"})
    fig.update_layout(yaxis_ticksuffix="%", height=280)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No trend data yet — run the pipeline with date-stamped reviews.")

st.divider()

col_l, col_r = st.columns(2)
with col_l:
    st.subheader("Reviews by Platform")
    if stats["by_platform"]:
        df_p = pd.DataFrame(
            list(stats["by_platform"].items()), columns=["Platform", "Reviews"]
        ).sort_values("Reviews", ascending=False)
        st.bar_chart(df_p.set_index("Platform"))

with col_r:
    st.subheader("Sentiment Breakdown")
    if stats["by_sentiment"]:
        df_s = pd.DataFrame(
            list(stats["by_sentiment"].items()), columns=["Sentiment", "Count"]
        )
        color_map = {
            "positive": "#4CAF50", "negative": "#F44336",
            "neutral": "#9E9E9E", "mixed": "#FF9800",
        }
        fig2 = px.pie(
            df_s, names="Sentiment", values="Count",
            color="Sentiment", color_discrete_map=color_map,
        )
        fig2.update_layout(height=280)
        st.plotly_chart(fig2, use_container_width=True)
