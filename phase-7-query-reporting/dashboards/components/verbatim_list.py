"""Reusable Streamlit component: renders a list of review verbatims."""
from __future__ import annotations
import streamlit as st


def verbatim_list(
    verbatims: list[dict],
    max_display: int = 10,
    show_platform: bool = True,
    show_rating: bool = True,
    show_date: bool = True,
) -> None:
    """Render a list of verbatim dicts. Each dict should have: verbatim, platform,
    normalized_rating, published_at keys (all optional except verbatim)."""
    if not verbatims:
        st.info("No reviews to display.")
        return

    displayed = verbatims[:max_display]
    for ev in displayed:
        text = ev.get("verbatim") or ev.get("clean_text") or ""
        if not text:
            continue
        meta_parts: list[str] = []
        if show_platform and ev.get("platform"):
            meta_parts.append(ev["platform"])
        if show_rating and ev.get("normalized_rating") is not None:
            meta_parts.append(f"★ {ev['normalized_rating']:.0f}")
        if show_date and ev.get("published_at"):
            meta_parts.append(ev["published_at"][:10])
        meta = " · ".join(meta_parts)
        st.markdown(f"> *{text}*" + (f"  \n— {meta}" if meta else ""))

    if len(verbatims) > max_display:
        st.caption(f"Showing {max_display} of {len(verbatims)} reviews.")
