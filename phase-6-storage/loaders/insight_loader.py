from __future__ import annotations
import json
import logging
from pathlib import Path
from .base_loader import BaseLoader

logger = logging.getLogger(__name__)


class InsightLoader(BaseLoader):
    """Loads all four Phase 5 artifact types from data/insights/."""

    def load_all(self) -> tuple[list[dict], int]:  # type: ignore[override]
        raise NotImplementedError("Use load_insights(), load_jtbd(), load_segments(), load_unmet_needs() directly")

    def _iter_glob(self, prefix: str) -> list[dict]:
        results: list[dict] = []
        if not self._data_dir.exists():
            return results
        for path in sorted(self._data_dir.glob(f"**/{prefix}*.jsonl")):
            results.extend(self._read_file(path))
        return results

    # ------------------------------------------------------------------
    # Product Insights
    # ------------------------------------------------------------------
    def load_insights(self) -> tuple[list[dict], list[dict], list[dict], int]:
        """Returns (insight_rows, insight_cluster_rows, insight_review_rows, skipped)."""
        insights: list[dict] = []
        ic_rows: list[dict] = []
        ir_rows: list[dict] = []
        skipped = 0

        for raw in self._iter_glob("product_insights"):
            if not raw.get("id"):
                skipped += 1
                continue
            insight_id = raw["id"]
            verbatims = raw.get("supporting_verbatims", [])
            insights.append({
                "id": insight_id,
                "title": raw.get("title", ""),
                "description": raw.get("description", ""),
                "insight_type": raw.get("insight_type", "problem"),
                "affected_segment": raw.get("affected_segment"),
                "frequency_score": raw.get("frequency_score"),
                "severity_score": raw.get("severity_score"),
                "uniqueness_score": raw.get("uniqueness_score"),
                "opportunity_score": raw.get("opportunity_score"),
                "confidence": raw.get("confidence", "low"),
                "confidence_score": raw.get("confidence_score", 0.0),
                "reasoning": raw.get("reasoning"),
                "discovery_friction_related": int(bool(raw.get("discovery_friction_related", False))),
                "trend_direction": raw.get("trend_direction"),
                "review_required": int(bool(raw.get("review_required", False))),
                "supporting_verbatims": json.dumps(verbatims),
                "generation_model": raw.get("generation_model"),
                "prompt_version": raw.get("prompt_version"),
                "generated_at": raw.get("generated_at", ""),
                "schema_version": raw.get("schema_version", "1.0"),
            })
            for cid in raw.get("supporting_cluster_ids", []):
                ic_rows.append({"insight_id": insight_id, "cluster_id": cid})
            for i, rev_id in enumerate(raw.get("supporting_review_ids", [])):
                ir_rows.append({
                    "insight_id": insight_id,
                    "review_id": rev_id,
                    "verbatim": verbatims[i] if i < len(verbatims) else None,
                })

        logger.info("Insight loader: %d insights, %d cluster links, %d review links, %d skipped",
                    len(insights), len(ic_rows), len(ir_rows), skipped)
        return insights, ic_rows, ir_rows, skipped

    # ------------------------------------------------------------------
    # JTBD Profiles
    # ------------------------------------------------------------------
    def load_jtbd(self) -> tuple[list[dict], int]:
        records: list[dict] = []
        skipped = 0
        for raw in self._iter_glob("jtbd_profiles"):
            if not raw.get("id"):
                skipped += 1
                continue
            records.append({
                "id": raw["id"],
                "job_statement": raw.get("job_statement", ""),
                "short_label": raw.get("short_label", ""),
                "supporting_cluster_ids": json.dumps(raw.get("supporting_cluster_ids", [])),
                "user_segments": json.dumps(raw.get("user_segments", [])),
                "frequency_estimate": raw.get("frequency_estimate"),
                "satisfaction_score": raw.get("satisfaction_score"),
                "gap_score": raw.get("gap_score"),
                "confidence_score": raw.get("confidence_score"),
                "gap_description": raw.get("gap_description"),
                "generated_at": raw.get("generated_at", ""),
                "generation_model": raw.get("generation_model"),
                "prompt_version": raw.get("prompt_version"),
                "schema_version": raw.get("schema_version", "1.0"),
            })
        logger.info("JTBD loader: %d loaded, %d skipped", len(records), skipped)
        return records, skipped

    # ------------------------------------------------------------------
    # User Segments
    # ------------------------------------------------------------------
    def load_segments(self) -> tuple[list[dict], int]:
        records: list[dict] = []
        skipped = 0
        for raw in self._iter_glob("user_segments"):
            if not raw.get("id"):
                skipped += 1
                continue
            records.append({
                "id": raw["id"],
                "segment_label": raw.get("segment_label", ""),
                "description": raw.get("description"),
                "behavioral_signals": json.dumps(raw.get("behavioral_signals", [])),
                "primary_jtbd": raw.get("primary_jtbd"),
                "primary_pain": raw.get("primary_pain"),
                "review_count": raw.get("review_count"),
                "fraction_of_total": raw.get("fraction_of_total"),
                "discovery_friction_rate": raw.get("discovery_friction_rate"),
                "platform_affinity": json.dumps(raw.get("platform_affinity", {})),
                "avg_sentiment_score": raw.get("avg_sentiment_score"),
                "top_features_mentioned": json.dumps(raw.get("top_features_mentioned", [])),
                "generated_at": raw.get("generated_at", ""),
                "generation_model": raw.get("generation_model"),
                "schema_version": raw.get("schema_version", "1.0"),
            })
        logger.info("UserSegment loader: %d loaded, %d skipped", len(records), skipped)
        return records, skipped

    # ------------------------------------------------------------------
    # Unmet Needs
    # ------------------------------------------------------------------
    def load_unmet_needs(self) -> tuple[list[dict], int]:
        records: list[dict] = []
        skipped = 0
        for raw in self._iter_glob("unmet_needs"):
            if not raw.get("id"):
                skipped += 1
                continue
            records.append({
                "id": raw["id"],
                "need_statement": raw.get("need_statement", ""),
                "supporting_cluster_ids": json.dumps(raw.get("supporting_cluster_ids", [])),
                "affected_segment": raw.get("affected_segment"),
                "expressed_frequency": raw.get("expressed_frequency"),
                "related_features": json.dumps(raw.get("related_features", [])),
                "gap_description": raw.get("gap_description"),
                "confidence_score": raw.get("confidence_score"),
                "linguistic_patterns_matched": json.dumps(raw.get("linguistic_patterns_matched", [])),
                "generated_at": raw.get("generated_at", ""),
                "generation_model": raw.get("generation_model"),
                "prompt_version": raw.get("prompt_version"),
                "schema_version": raw.get("schema_version", "1.0"),
            })
        logger.info("UnmetNeed loader: %d loaded, %d skipped", len(records), skipped)
        return records, skipped
