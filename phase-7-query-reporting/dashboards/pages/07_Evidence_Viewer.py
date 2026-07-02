"""Page 7 — Evidence Viewer: drill into insight → cluster → review lineage."""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st

from dashboards.db import (
    fetch_insights,
    fetch_clusters,
    fetch_insight_evidence,
    fetch_cluster_evidence,
    get_connection,
)

st.set_page_config(page_title="Evidence Viewer", layout="wide")
st.title("Evidence Viewer")
st.caption(
    "Trace any insight or cluster back to the verbatims that support it. "
    "Every finding here links to real customer reviews."
)

# ── Mode selector ─────────────────────────────────────────────────────────────
mode = st.radio("View by", ["Insight", "Cluster"], horizontal=True)

st.divider()

if mode == "Insight":
    insights = fetch_insights(review_required=None, limit=200)
    if not insights:
        st.info("No insights found. Run Phases 1–6 first.")
        st.stop()

    # Optional: filter pending review
    show_pending = st.checkbox("Include insights pending review", value=False)
    if not show_pending:
        insights = [i for i in insights if not i.get("review_required")]

    titles = list(dict.fromkeys(i["title"] for i in insights))
    selected_title = st.selectbox("Select insight", ["(none)"] + titles)

    if selected_title != "(none)":
        ins = next((i for i in insights if i["title"] == selected_title), None)
        if ins:
            # Header metrics
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Opportunity Score", f"{ins.get('opportunity_score', 0):.3f}")
            c2.metric("Confidence", ins.get("confidence", "—"))
            c3.metric("Type", ins.get("insight_type", "—"))
            c4.metric("Segment", ins.get("affected_segment") or "—")

            st.markdown(f"**Description:** {ins.get('description', '')}")
            if ins.get("reasoning"):
                st.markdown(f"**Reasoning:** {ins['reasoning']}")
            if ins.get("trend_direction"):
                st.markdown(f"**Trend:** {ins['trend_direction']}")
            if ins.get("review_required"):
                st.warning("This insight is pending human review (confidence below threshold).")

            st.divider()

            # Evidence
            evidence = fetch_insight_evidence(ins["id"])
            verbatims = evidence.get("verbatims", [])
            cluster_ids = evidence.get("cluster_ids", [])

            st.subheader(f"Supporting Evidence ({len(verbatims)} verbatims)")
            if verbatims:
                for ev in verbatims:
                    rating = f"★ {ev['normalized_rating']:.0f}" if ev.get("normalized_rating") else ""
                    st.markdown(
                        f"> *{ev['verbatim']}*  \n"
                        f"— {ev.get('platform', 'unknown')} {rating} · {(ev.get('published_at') or '')[:10]}"
                    )
            else:
                st.info("No verbatims stored directly. Evidence comes from linked clusters.")

            if cluster_ids:
                st.divider()
                st.subheader(f"Lineage: Supporting Clusters ({len(cluster_ids)})")
                st.caption("Insight → Clusters → Reviews")
                all_clusters = fetch_clusters()
                cluster_label_map = {c["id"]: c.get("label") or c["id"][:16] for c in all_clusters}
                for cid in cluster_ids[:5]:
                    cluster_evidence = fetch_cluster_evidence(cid, limit=3)
                    label = cluster_label_map.get(cid, cid[:16] + "…")
                    with st.expander(label):
                        for ev in cluster_evidence:
                            st.markdown(
                                f"> *{ev['verbatim']}*  \n"
                                f"— {ev.get('platform', '')} · {(ev.get('published_at') or '')[:10]}"
                            )

else:  # Cluster mode
    clusters = fetch_clusters()
    if not clusters:
        st.info("No clusters found. Run Phase 4 first.")
        st.stop()

    labels = list(dict.fromkeys(c["label"] for c in clusters))
    selected_label = st.selectbox("Select cluster", ["(none)"] + labels)

    if selected_label != "(none)":
        cluster = next((c for c in clusters if c["label"] == selected_label), None)
        if cluster:
            c1, c2, c3 = st.columns(3)
            c1.metric("Size", cluster.get("size", "—"))
            c2.metric("Avg Sentiment", f"{cluster.get('avg_sentiment_score', 0):.2f}" if cluster.get("avg_sentiment_score") is not None else "—")
            c3.metric("Friction Rate", f"{cluster.get('discovery_friction_rate', 0):.0%}" if cluster.get("discovery_friction_rate") is not None else "—")

            st.markdown(f"**Theme:** {cluster.get('theme', '')}")
            st.markdown(
                f"**Trend:** {cluster.get('trend_direction', '—')} | "
                f"**Platform:** {cluster.get('dominant_platform', '—')} | "
                f"**Emotion:** {cluster.get('dominant_emotion', '—')}"
            )

            st.divider()
            st.subheader("Representative Reviews")
            evidence = fetch_cluster_evidence(cluster["id"], limit=10)
            if evidence:
                for ev in evidence:
                    badge = " **[Rep]**" if ev.get("is_representative") else ""
                    rating = f"★ {ev['normalized_rating']:.0f}" if ev.get("normalized_rating") else ""
                    st.markdown(
                        f"> *{ev['verbatim']}*{badge}  \n"
                        f"— {ev.get('platform', '')} {rating} · {(ev.get('published_at') or '')[:10]}"
                    )
            else:
                st.info("No review text found for this cluster's members.")
