"""Reusable Streamlit component: evidence panel showing lineage chain."""
from __future__ import annotations
import streamlit as st


def evidence_panel(evidence: dict, title: str = "Evidence", cluster_label_map: dict | None = None) -> None:
    """Render cluster labels + verbatims for an insight."""
    verbatims = evidence.get("verbatims", [])
    cluster_ids = evidence.get("cluster_ids", [])

    st.subheader(title)

    if cluster_ids:
        _map = cluster_label_map or {}
        names = [_map.get(cid, cid[:8]) for cid in cluster_ids[:5]]
        suffix = f" + {len(cluster_ids) - 5} more" if len(cluster_ids) > 5 else ""
        st.caption(f"Linked clusters: {', '.join(names)}{suffix}")

    if verbatims:
        st.markdown(f"**{len(verbatims)} supporting reviews:**")
        for ev in verbatims:
            rating = f"★ {ev['normalized_rating']:.0f}" if ev.get("normalized_rating") else ""
            platform = ev.get("platform", "")
            date = (ev.get("published_at") or "")[:10]
            st.markdown(
                f"> *{ev['verbatim']}*  \n— {platform} {rating} · {date}"
            )
    else:
        st.info("No verbatims stored for this item. See linked clusters for evidence.")
