"""Page 5 — Segment Explorer: per-segment breakdown and cross-segment comparison."""
from __future__ import annotations
import json
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

# ── Helpers ───────────────────────────────────────────────────────────────────

_LABEL_MAP = {
    "power_user": "Power User",
    "casual": "Casual Listener",
    "new": "New User",
    "churned": "Churned User",
    "unknown": "Unclassified",
}


def _pretty_label(raw: str) -> str:
    return _LABEL_MAP.get(raw, raw.replace("_", " ").title())


def _parse_json_list(raw) -> list:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _parse_json_str(raw) -> str | None:
    """Unwrap a JSON-encoded string like '\"unknown\"' → 'unknown'."""
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
        return str(parsed) if parsed else None
    except (json.JSONDecodeError, TypeError):
        return str(raw)


def _is_placeholder_description(text: str | None) -> bool:
    if not text:
        return True
    return "LLM description unavailable" in text or text.strip() in ("", "...")


df = pd.DataFrame(segments)

# ── Cross-segment comparison ──────────────────────────────────────────────────
st.subheader("Cross-Segment Comparison")
compare_cols = [c for c in [
    "segment_label", "review_count", "fraction_of_total",
    "discovery_friction_rate", "avg_sentiment_score",
] if c in df.columns]

if compare_cols:
    df_display = df[compare_cols].copy()
    if "segment_label" in df_display.columns:
        df_display["segment_label"] = df_display["segment_label"].apply(_pretty_label)
    df_display = df_display.rename(columns={
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
    df_chart = df.dropna(subset=["discovery_friction_rate"]).copy()
    if not df_chart.empty:
        df_chart["display_label"] = df_chart["segment_label"].apply(_pretty_label)
        st.subheader("Discovery Friction Rate by Segment")
        fig = px.bar(
            df_chart,
            x="display_label",
            y="discovery_friction_rate",
            labels={"display_label": "Segment", "discovery_friction_rate": "Friction Rate"},
            color="discovery_friction_rate",
            color_continuous_scale="Reds",
        )
        fig.update_layout(yaxis_tickformat=".0%", height=300, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── Per-segment drill-down ────────────────────────────────────────────────────
st.subheader("Per-Segment Profile")
raw_labels = list(dict.fromkeys(df["segment_label"].tolist())) if "segment_label" in df.columns else []
pretty_to_raw = {_pretty_label(r): r for r in raw_labels}
pretty_labels = [_pretty_label(r) for r in raw_labels]

selected_pretty = st.selectbox("Select segment →", ["(none)"] + pretty_labels)

if selected_pretty != "(none)":
    raw_selected = pretty_to_raw.get(selected_pretty, selected_pretty)
    matches = df[df["segment_label"] == raw_selected]
    if matches.empty:
        st.warning("No data for this segment.")
    else:
        row = matches.iloc[0].to_dict()

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Reviews", row.get("review_count", "—"))
        fraction = row.get("fraction_of_total")
        col2.metric("% of Users", f"{fraction:.1%}" if fraction is not None else "—")
        col3.metric(
            "Friction Rate",
            f"{row.get('discovery_friction_rate', 0):.1%}"
            if row.get("discovery_friction_rate") is not None else "—",
        )
        col4.metric(
            "Avg Sentiment",
            f"{row.get('avg_sentiment_score', 0):.2f}"
            if row.get("avg_sentiment_score") is not None else "—",
        )

        desc = row.get("description")
        if not _is_placeholder_description(desc):
            st.markdown(f"**Description:** {desc}")

        if row.get("primary_jtbd"):
            st.markdown(f"**Primary JTBD:** {row['primary_jtbd']}")
        if row.get("primary_pain"):
            st.markdown(f"**Primary pain point:** {row['primary_pain']}")

        features = _parse_json_list(row.get("top_features_mentioned"))
        if features:
            st.markdown(f"**Top features mentioned:** {', '.join(features)}")

        signals = _parse_json_list(row.get("behavioral_signals"))
        if signals:
            st.markdown("**Behavioral signals:**")
            for s in signals:
                st.markdown(f"- {s}")

        platform = _parse_json_str(row.get("platform_affinity"))
        if platform and platform.lower() not in ("unknown", "none", ""):
            st.markdown(f"**Platform affinity:** {platform}")

        st.caption(
            f"Segment last updated: {(row.get('generated_at') or '')[:10]} "
            f"· model: {row.get('generation_model', '—')}"
        )
