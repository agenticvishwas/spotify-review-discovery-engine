"""Page 4 — Opportunity List: ranked product opportunities with evidence drill-down."""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboards.db import fetch_insights, fetch_insight_evidence

st.set_page_config(page_title="Opportunity List", layout="wide")
st.title("Opportunity List")
st.caption("Product opportunities ranked by composite opportunity score.")

_TYPE_LABELS = {"jtbd": "JTBD", "problem": "Problem", "segment": "Segment"}
_SEG_LABELS = {
    "power_user": "Power User", "casual": "Casual Listener",
    "new": "New User", "churned": "Churned User",
    "unknown": "Unclassified", "all": "All Segments",
}


def _pretty_type(raw: str | None) -> str:
    return _TYPE_LABELS.get(raw or "", (raw or "").replace("_", " ").title())


def _pretty_seg(raw: str | None) -> str:
    return _SEG_LABELS.get(raw or "", (raw or "—").replace("_", " ").title())


# ── Filters ───────────────────────────────────────────────────────────────────
col_f1, col_f2, col_f3 = st.columns(3)
with col_f1:
    seg_filter = st.text_input("Filter by segment", "")
with col_f2:
    # Only offer types that actually exist in the knowledge base.
    type_options = ["all", "jtbd", "problem", "segment"]
    type_labels = {"all": "All types", "jtbd": "JTBD", "problem": "Problem", "segment": "Segment"}
    type_filter = st.selectbox("Insight type", type_options, format_func=lambda t: type_labels.get(t, t))
with col_f3:
    disc_only = st.checkbox("Discovery-related only")

# ── Load + filter ─────────────────────────────────────────────────────────────
all_insights = fetch_insights(review_required=0, limit=200)

if type_filter != "all":
    all_insights = [i for i in all_insights if i.get("insight_type") == type_filter]
if seg_filter:
    all_insights = [
        i for i in all_insights
        if seg_filter.lower() in (i.get("affected_segment") or "").lower()
    ]
if disc_only:
    all_insights = [i for i in all_insights if i.get("discovery_friction_related")]

st.markdown(f"**{len(all_insights)} opportunities** match filters.")

if not all_insights:
    st.info("No insights match your filters. Adjust and try again.")
    st.stop()

# ── Summary chart — one bar per unique title (highest score wins) ─────────────
df_all = pd.DataFrame(all_insights)
if "opportunity_score" in df_all.columns and "title" in df_all.columns:
    df_chart = (
        df_all
        .sort_values("opportunity_score", ascending=False)
        .drop_duplicates(subset=["title"], keep="first")
        .head(30)
        .copy()
    )
    df_chart["label"] = df_chart["title"].str[:50]
    df_chart = df_chart.sort_values("opportunity_score", ascending=True)
    fig = px.bar(
        df_chart,
        x="opportunity_score",
        y="label",
        orientation="h",
        color="confidence",
        labels={"opportunity_score": "Opportunity Score", "label": ""},
        color_discrete_map={"high": "#4CAF50", "medium": "#FF9800", "low": "#9E9E9E"},
    )
    fig.update_layout(height=max(300, min(len(df_chart), 30) * 28), showlegend=True)
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── Evidence drill-down ───────────────────────────────────────────────────────
st.subheader("Drill into an opportunity")
titles = list(dict.fromkeys(i["title"] for i in all_insights[:50]))
selected = st.selectbox("Select insight →", ["(none)"] + titles)

if selected != "(none)":
    ins = next((i for i in all_insights if i["title"] == selected), None)
    if ins:
        c1, c2, c3 = st.columns(3)
        c1.metric("Opportunity Score", f"{ins.get('opportunity_score', 0):.3f}")
        c2.metric("Frequency", f"{ins.get('frequency_score', 0):.3f}")
        c3.metric("Severity", f"{ins.get('severity_score', 0):.3f}")

        st.markdown(
            f"**Type:** {_pretty_type(ins.get('insight_type'))} "
            f"| **Segment:** {_pretty_seg(ins.get('affected_segment'))} "
            f"| **Confidence:** {(ins.get('confidence') or '—').title()}"
        )
        st.markdown(f"**Description:** {ins.get('description', '')}")
        if ins.get("reasoning"):
            st.caption(f"Reasoning: {ins['reasoning']}")

        evidence = fetch_insight_evidence(ins["id"])
        verbatims = evidence.get("verbatims", [])
        if verbatims:
            st.markdown(f"**Supporting evidence ({len(verbatims)} reviews):**")
            for ev in verbatims[:8]:
                rating = f"★ {ev['normalized_rating']:.0f}" if ev.get("normalized_rating") else ""
                st.markdown(
                    f"> *{ev['verbatim']}*  \n"
                    f"— {ev.get('platform', '')} {rating} · {(ev.get('published_at') or '')[:10]}"
                )
        else:
            st.info("No verbatims stored for this insight. Evidence is in linked clusters.")

        if evidence.get("cluster_ids"):
            st.caption(f"Supporting cluster IDs: {', '.join(evidence['cluster_ids'][:5])}")
