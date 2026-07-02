"""Page 2 — Discovery Insights: friction themes, clusters, and rates."""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboards.db import (
    fetch_clusters,
    fetch_discovery_trend,
    fetch_insights,
    fetch_cluster_evidence,
)

st.set_page_config(page_title="Discovery Insights", layout="wide")
st.title("Discovery Insights")
st.caption("Themes and patterns where users struggle to discover new music.")

# ── Friction trend ────────────────────────────────────────────────────────────
trend = fetch_discovery_trend()
if trend:
    df = pd.DataFrame(trend)
    df["friction_rate"] = df.apply(
        lambda r: round(r["friction"] / r["total"] * 100, 1) if r["total"] > 0 else 0,
        axis=1,
    )
    df["day"] = pd.to_datetime(df["day"])
    st.subheader("Discovery Friction Rate — Rolling Trend")
    fig = px.area(
        df.tail(90), x="day", y="friction_rate",
        labels={"friction_rate": "Friction %", "day": "Date"},
    )
    fig.update_layout(yaxis_ticksuffix="%", height=260)
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── Discovery clusters ────────────────────────────────────────────────────────
clusters = fetch_clusters(discovery_only=True)
if clusters:
    st.subheader(f"Discovery-Related Clusters ({len(clusters)})")
    df_c = pd.DataFrame(clusters)[
        ["label", "theme", "size", "avg_sentiment_score", "discovery_friction_rate", "trend_direction"]
    ].rename(columns={
        "label": "Label", "theme": "Theme", "size": "Reviews",
        "avg_sentiment_score": "Avg Sentiment", "discovery_friction_rate": "Friction Rate",
        "trend_direction": "Trend",
    })
    st.dataframe(df_c, use_container_width=True, hide_index=True)

    selected = st.selectbox("Drill into cluster →", ["(none)"] + list(dict.fromkeys(c["label"] for c in clusters)))
    if selected != "(none)":
        cluster = next((c for c in clusters if c["label"] == selected), None)
        if cluster:
            st.markdown(f"**Theme:** {cluster['theme']}")
            st.markdown(f"**Size:** {cluster['size']} reviews | **Friction Rate:** {cluster.get('discovery_friction_rate', 0):.0%}")
            evidence = fetch_cluster_evidence(cluster["id"], limit=5)
            if evidence:
                st.markdown("**Representative reviews:**")
                for ev in evidence:
                    rating = f"★ {ev['normalized_rating']:.0f}" if ev.get("normalized_rating") else ""
                    st.markdown(
                        f"> *{ev['verbatim']}*  \n"
                        f"— {ev.get('platform', '')} {rating} · {(ev.get('published_at') or '')[:10]}"
                    )
else:
    st.info("No discovery-related clusters found. Run Phases 4–5 to generate clusters.")

st.divider()

# ── Discovery insights ────────────────────────────────────────────────────────
insights = fetch_insights(review_required=0)
disc_insights = [i for i in insights if i.get("discovery_friction_related")]
st.subheader(f"Discovery-Related Insights ({len(disc_insights)})")
if disc_insights:
    for ins in disc_insights[:10]:
        conf = ins.get("confidence", "")
        score = ins.get("opportunity_score", 0) or 0
        with st.expander(f"{ins['title']} — score {score:.2f} ({conf})"):
            st.write(ins.get("description", ""))
            if ins.get("reasoning"):
                st.caption(f"Reasoning: {ins['reasoning']}")
else:
    st.info("No discovery-related insights yet.")
