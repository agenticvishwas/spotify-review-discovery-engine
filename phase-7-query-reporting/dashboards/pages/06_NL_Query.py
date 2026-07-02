"""Page 6 — NL Query Interface: ask questions in natural language."""
from __future__ import annotations
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st

from config import Phase7Config
from dashboards.db import get_connection
from query_engine.intent_classifier import IntentClassifier
from query_engine.query_planner import QueryPlanner
from query_engine.query_executor import QueryExecutor
from query_engine.evidence_retriever import EvidenceRetriever
from query_engine.answer_synthesizer import AnswerSynthesizer
from query_engine.llm_factory import build_llm_provider, configured_provider_names

st.set_page_config(page_title="NL Query", layout="wide")
st.title("Natural Language Query")
st.caption(
    "Ask any question about the review data. The engine classifies your intent, "
    "queries the knowledge base, and synthesises an evidence-backed answer."
)

# ── LLM setup ─────────────────────────────────────────────────────────────────
# Supports Anthropic, Groq, and Ollama — set ANTHROPIC_API_KEY / GROQ_API_KEY /
# OLLAMA_BASE_URL (or OLLAMA_MODEL) to enable one or more. With more than one
# configured, calls fail over automatically (see query_engine/llm_factory.py).
@st.cache_resource
def _get_llm():
    config = Phase7Config.from_env()
    return build_llm_provider(config), configured_provider_names(config)


llm, active_providers = _get_llm()
if llm is None:
    st.warning(
        "No LLM provider configured — answer synthesis is disabled. "
        "Set ANTHROPIC_API_KEY, GROQ_API_KEY, or OLLAMA_BASE_URL/OLLAMA_MODEL "
        "and restart the dashboard to enable NL answers."
    )
else:
    st.caption(f"Answer synthesis providers (priority order): {', '.join(active_providers)}")

# ── Example questions ─────────────────────────────────────────────────────────
st.markdown("**Example questions:**")
examples = [
    "Why do users struggle to discover new music?",
    "What are the top 5 product opportunities?",
    "What do power users complain about most?",
    "Which problems are getting worse over time?",
    "What jobs are users trying to accomplish?",
]
cols = st.columns(len(examples))
question = st.session_state.get("nl_question", "")
for i, ex in enumerate(examples):
    if cols[i].button(ex[:35] + "…" if len(ex) > 35 else ex, use_container_width=True):
        question = ex
        st.session_state["nl_question"] = question

# ── Query input ───────────────────────────────────────────────────────────────
st.divider()
question = st.text_input(
    "Your question",
    value=question,
    placeholder="e.g. Why do users find music discovery repetitive?",
)

run = st.button("Search", type="primary", disabled=not question)

if run and question:
    conn = get_connection()
    classifier = IntentClassifier()
    planner = QueryPlanner()
    executor = QueryExecutor(conn)
    retriever = EvidenceRetriever(conn)

    with st.spinner("Classifying intent and querying knowledge base..."):
        classified = classifier.classify(question)
        plan = planner.build(classified, question)
        results = executor.execute(plan, raw_question=question)

    # Collect all insight IDs and verbatims from results
    all_verbatims: list[dict] = []
    for step in results["steps"]:
        if step["table"] == "insights":
            for row in step["rows"][:3]:
                vbs = retriever.for_insight(row["id"], limit=3)
                all_verbatims.extend(vbs)
        elif step["table"] == "clusters":
            for row in step["rows"][:3]:
                vbs = retriever.for_cluster(row["id"], limit=3)
                all_verbatims.extend(vbs)
        elif step["kind"] == "vector_search":
            for row in step["rows"]:
                if row.get("document"):
                    all_verbatims.append({"verbatim": row["document"], "platform": "vector_result"})

    # ── Answer synthesis ──────────────────────────────────────────────────────
    col_ans, col_ev = st.columns([3, 2])

    with col_ans:
        st.subheader("Answer")
        st.caption(
            f"Intent detected: **{classified.intent.value}** "
            f"(confidence {classified.confidence:.0%})"
            + (f" | Entity: `{classified.extracted_entity}`" if classified.extracted_entity else "")
        )

        if llm:
            with st.spinner("Synthesising answer..."):
                synthesizer = AnswerSynthesizer(llm)
                answer = synthesizer.synthesize(question, results, all_verbatims)

            st.markdown(answer.get("answer", "No answer generated."))

            conf = answer.get("confidence", "")
            conf_color = {"high": "green", "medium": "orange", "low": "red"}.get(conf, "grey")
            st.markdown(f"**Confidence:** :{conf_color}[{conf}]")

            if answer.get("key_findings"):
                st.markdown("**Key findings:**")
                for f in answer["key_findings"]:
                    with st.expander(f.get("finding", "Finding")):
                        for v in f.get("verbatims", []):
                            st.markdown(f"> *{v}*")

            if answer.get("caveats"):
                st.warning(f"Caveat: {answer['caveats']}")

            # Export
            export_json = json.dumps(answer, indent=2, default=str)
            st.download_button("Export answer (JSON)", export_json, "query_answer.json", "application/json")
        else:
            st.info("LLM synthesis disabled. Showing raw query results below.")

    with col_ev:
        st.subheader("Evidence")
        total_rows = sum(s["count"] for s in results["steps"])
        st.caption(f"{total_rows} records retrieved across {len(results['steps'])} query steps.")

        for step in results["steps"]:
            if not step["rows"]:
                continue
            with st.expander(f"{step['description']} ({step['count']})"):
                for row in step["rows"][:5]:
                    text = (
                        row.get("verbatim") or row.get("clean_text") or
                        row.get("title") or row.get("job_statement") or
                        row.get("document") or str(row.get("id", ""))
                    )
                    platform = row.get("platform", "")
                    st.markdown(f"• {text[:200]}" + (f" *({platform})*" if platform else ""))
