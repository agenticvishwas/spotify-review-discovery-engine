"""Page 3 — JTBD Map: jobs-to-be-done profiles and gap analysis."""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboards.db import fetch_jtbd

st.set_page_config(page_title="JTBD Map", layout="wide")
st.title("Jobs-to-Be-Done Map")
st.caption("Jobs users are trying to accomplish — satisfaction gaps reveal the biggest opportunities.")

jtbd = fetch_jtbd()

if not jtbd:
    st.info("No JTBD profiles yet. Run Phase 5 (Insight Generation) to populate.")
    st.stop()

df = pd.DataFrame(jtbd)

# ── Summary table ─────────────────────────────────────────────────────────────
st.subheader(f"All JTBD Profiles ({len(df)})")
display_cols = [c for c in ["short_label", "job_statement", "satisfaction_score", "gap_score",
                              "frequency_estimate", "user_segments", "confidence_score"] if c in df.columns]
df_display = df[display_cols].rename(columns={
    "short_label": "Label",
    "job_statement": "Job Statement",
    "satisfaction_score": "Satisfaction",
    "gap_score": "Gap Score",
    "frequency_estimate": "Est. Reviews",
    "user_segments": "Segments",
    "confidence_score": "Confidence",
})
st.dataframe(df_display, use_container_width=True, hide_index=True)

st.divider()

# ── Gap analysis chart ────────────────────────────────────────────────────────
if "gap_score" in df.columns and "short_label" in df.columns:
    df_sorted = df.dropna(subset=["gap_score"]).sort_values("gap_score", ascending=True)
    st.subheader("Gap Analysis — Highest Unmet Gaps")
    fig = px.bar(
        df_sorted,
        x="gap_score",
        y="short_label",
        orientation="h",
        labels={"gap_score": "Gap Score (higher = more unmet)", "short_label": "Job"},
        color="gap_score",
        color_continuous_scale="Reds",
    )
    fig.update_layout(height=max(300, len(df_sorted) * 30), showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── Drill into a job ──────────────────────────────────────────────────────────
labels = df["short_label"].tolist() if "short_label" in df.columns else []
selected = st.selectbox("Drill into a job →", ["(none)"] + labels)
if selected != "(none)":
    row = df[df["short_label"] == selected].iloc[0].to_dict()
    st.markdown(f"### {row.get('job_statement', selected)}")
    col1, col2, col3 = st.columns(3)
    col1.metric("Satisfaction", f"{row.get('satisfaction_score', 0):.2f}" if row.get('satisfaction_score') is not None else "—")
    col2.metric("Gap Score", f"{row.get('gap_score', 0):.2f}" if row.get('gap_score') is not None else "—")
    col3.metric("Est. Reviews", row.get("frequency_estimate", "—"))
    if row.get("gap_description"):
        st.markdown(f"**Gap description:** {row['gap_description']}")
    if row.get("user_segments"):
        st.markdown(f"**Relevant segments:** {row['user_segments']}")
