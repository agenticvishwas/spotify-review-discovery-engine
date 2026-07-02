"""Reusable Streamlit component: renders a ProductInsight as a card."""
from __future__ import annotations
import streamlit as st


def insight_card(ins: dict, show_evidence: bool = False, evidence: dict | None = None) -> None:
    """Render a single insight as a Streamlit expander card."""
    score = ins.get("opportunity_score", 0) or 0
    conf = ins.get("confidence", "")
    conf_icon = {"high": "✅", "medium": "⚠️", "low": "🔴"}.get(conf, "")
    segment = ins.get("affected_segment") or "—"
    itype = ins.get("insight_type", "")

    header = f"{conf_icon} **{ins.get('title', 'Untitled')}** — score {score:.2f} | {itype} | {segment}"
    with st.expander(header):
        st.markdown(ins.get("description", ""))
        if ins.get("reasoning"):
            st.caption(f"Reasoning: {ins['reasoning']}")
        if ins.get("trend_direction"):
            st.caption(f"Trend: {ins['trend_direction']}")

        c1, c2, c3 = st.columns(3)
        c1.metric("Opportunity", f"{score:.3f}")
        c2.metric("Frequency", f"{ins.get('frequency_score', 0) or 0:.3f}")
        c3.metric("Severity", f"{ins.get('severity_score', 0) or 0:.3f}")

        if show_evidence and evidence:
            verbatims = evidence.get("verbatims", [])
            if verbatims:
                st.markdown("**Supporting verbatims:**")
                for ev in verbatims[:5]:
                    rating = f"★ {ev['normalized_rating']:.0f}" if ev.get("normalized_rating") else ""
                    st.markdown(
                        f"> *{ev['verbatim']}*  \n"
                        f"— {ev.get('platform', '')} {rating}"
                    )
