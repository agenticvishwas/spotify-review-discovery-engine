"""Page 5 — Segment Explorer: per-segment breakdown and cross-segment comparison."""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboards.db import fetch_segments, get_connection

st.set_page_config(page_title="Segment Explorer", layout="wide")
st.title("Segment Explorer")
st.caption("User segment profiles and cross-segment discovery friction comparison.")

segments = fetch_segments()

if not segments:
    st.info("No user segment profiles yet. Run Phase 5 to generate segment data.")
    st.stop()

df = pd.DataFrame(segments)

# ── Cross-segment comparison ──────────────────────────────────────────────────
st.subheader("Cross-Segment Comparison")
compare_cols = [c for c in [
    "segment_label", "review_count", "fraction_of_total",
    "discovery_friction_rate", "avg_sentiment_score",
] if c in df.columns]

if compare_cols:
    df_display = df[compare_cols].rename(columns={
        "segment_label": "Segment",
        "review_count": "Reviews",
        "fraction_of_total": "% of Total",
        "discovery_friction_rate": "Friction Rate",
        "avg_sentiment_score": "Avg Sentiment",
    })
    if "% of Total" in df_display.columns:
        df_display["% of Total"] = df_display["% of Total"].apply(
            lambda v: f"{v:.1%}" if pd.notna(v) else "—"
        )
    if "Friction Rate" in df_display.columns:
        df_display["Friction Rate"] = df_display["Friction Rate"].apply(
            lambda v: f"{v:.1%}" if pd.notna(v) else "—"
        )
    st.dataframe(df_display, use_container_width=True, hide_index=True)

# ── Friction rate by segment chart ────────────────────────────────────────────
if "discovery_friction_rate" in df.columns and "segment_label" in df.columns:
    df_chart = df.dropna(subset=["discovery_friction_rate"])
    if not df_chart.empty:
        fig = px.bar(
            df_chart,
            x="segment_label",
            y="discovery_friction_rate",
            labels={"segment_label": "Segment", "discovery_friction_rate": "Friction Rate"},
            color="discovery_friction_rate",
            color_continuous_scale="Reds",
        )
        fig.update_layout(yaxis_tickformat=".0%", height=300, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── Per-segment drill-down ────────────────────────────────────────────────────
st.subheader("Per-Segment Profile")
seg_labels = df["segment_label"].tolist() if "segment_label" in df.columns else []
selected = st.selectbox("Select segment →", ["(none)"] + seg_labels)

if selected != "(none)":
    row = df[df["segment_label"] == selected].iloc[0].to_dict()
    col1, col2, col3 = st.columns(3)
    col1.metric("Reviews", row.get("review_count", "—"))
    col2.metric("Friction Rate", f"{row.get('discovery_friction_rate', 0):.1%}" if row.get("discovery_friction_rate") is not None else "—")
    col3.metric("Avg Sentiment", f"{row.get('avg_sentiment_score', 0):.2f}" if row.get("avg_sentiment_score") is not None else "—")

    if row.get("description"):
        st.markdown(f"**Description:** {row['description']}")
    if row.get("primary_jtbd"):
        st.markdown(f"**Primary JTBD:** {row['primary_jtbd']}")
    if row.get("primary_pain"):
        st.markdown(f"**Primary pain point:** {row['primary_pain']}")
    if row.get("top_features_mentioned"):
        st.markdown(f"**Top features mentioned:** {row['top_features_mentioned']}")
    if row.get("platform_affinity"):
        st.markdown(f"**Platform affinity:** {row['platform_affinity']}")
    if row.get("behavioral_signals"):
        st.markdown(f"**Behavioral signals:** {row['behavioral_signals']}")
