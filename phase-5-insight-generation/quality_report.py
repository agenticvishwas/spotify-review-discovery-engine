"""Phase 5 quality report generator.

Produces the insight_quality_report.json that the spec requires:
  - run statistics
  - insight counts per type
  - confidence distribution
  - top opportunity score
  - discovery-related insight count
"""

import statistics
from schemas.product_insight import JTBDProfile, ProductInsight, UnmetNeed, UserSegment


def build_quality_report(
    run_date: str,
    batch_id: str,
    clusters: list[dict],
    eligible_clusters: list[dict],
    product_insights: list[ProductInsight],
    jtbd_profiles: list[JTBDProfile],
    user_segments: list[UserSegment],
    unmet_needs: list[UnmetNeed],
    providers: list[str],
) -> dict:
    """Build the quality report dict for Phase 5."""

    # Separate insight types
    opp_insights = [i for i in product_insights if i.insight_type == "opportunity"]
    jtbd_insights = [i for i in product_insights if i.insight_type == "jtbd"]
    problem_insights = [i for i in product_insights if i.insight_type == "problem"]
    unmet_insights = [i for i in product_insights if i.insight_type == "unmet_need"]
    segment_insights = [i for i in product_insights if i.insight_type == "segment"]

    all_opp_scores = [i.opportunity_score for i in product_insights]
    all_conf_scores = [i.confidence_score for i in product_insights]

    low_confidence = [i for i in product_insights if i.review_required]
    discovery_related = [i for i in product_insights if i.discovery_friction_related]

    trend_counts: dict[str, int] = {"increasing": 0, "stable": 0, "decreasing": 0}
    for ins in product_insights:
        trend_counts[ins.trend_direction] = trend_counts.get(ins.trend_direction, 0) + 1

    conf_dist = {
        "high": sum(1 for i in product_insights if i.confidence == "high"),
        "medium": sum(1 for i in product_insights if i.confidence == "medium"),
        "low": sum(1 for i in product_insights if i.confidence == "low"),
    }

    report = {
        "run_date": run_date,
        "batch_id": batch_id,
        "providers_used": providers,
        "total_clusters_analyzed": len(clusters),
        "eligible_clusters": len(eligible_clusters),
        "micro_clusters_skipped": len(clusters) - len(eligible_clusters),
        "insights_generated": {
            "product_insights": len(product_insights),
            "opportunities": len(opp_insights),
            "jtbd_insights": len(jtbd_insights),
            "problems": len(problem_insights),
            "unmet_needs_as_insights": len(unmet_insights),
            "segment_insights": len(segment_insights),
            "jtbd_profiles": len(jtbd_profiles),
            "user_segments": len(user_segments),
            "unmet_needs": len(unmet_needs),
        },
        "top_opportunity_score": round(max(all_opp_scores, default=0.0), 4),
        "avg_opportunity_score": round(
            statistics.mean(all_opp_scores) if all_opp_scores else 0.0, 4
        ),
        "avg_confidence_score": round(
            statistics.mean(all_conf_scores) if all_conf_scores else 0.0, 4
        ),
        "confidence_distribution": conf_dist,
        "low_confidence_insights": len(low_confidence),
        "low_confidence_rate": round(
            len(low_confidence) / max(len(product_insights), 1), 4
        ),
        "discovery_related_insights": len(discovery_related),
        "trend_distribution": trend_counts,
        "quality_flags": _quality_flags(product_insights, jtbd_profiles, unmet_needs),
    }
    return report


def _quality_flags(
    insights: list[ProductInsight],
    jtbd_profiles: list[JTBDProfile],
    unmet_needs: list[UnmetNeed],
) -> list[str]:
    """Return list of quality warnings for the PM to be aware of."""
    flags: list[str] = []

    if not insights:
        flags.append("WARNING: No product insights generated — check cluster input quality.")

    low_conf_rate = sum(1 for i in insights if i.review_required) / max(len(insights), 1)
    if low_conf_rate > 0.5:
        flags.append(
            f"WARNING: {low_conf_rate:.0%} of insights are low-confidence. "
            "Consider lowering batch_size or using a higher-quality provider."
        )

    evidence_gaps = sum(1 for i in insights if len(i.supporting_review_ids) < 3)
    if evidence_gaps:
        flags.append(
            f"WARNING: {evidence_gaps} insights have fewer than 3 supporting verbatims. "
            "Ensure Phase 3 analyzed_reviews are available for evidence mapping."
        )

    if not jtbd_profiles:
        flags.append("INFO: No JTBD profiles generated. Check cluster themes contain jtbd_signal data.")

    if not unmet_needs:
        flags.append("INFO: No unmet needs detected. Reviews may not contain desire-expression patterns.")

    if not flags:
        flags.append("OK: All quality checks passed.")

    return flags
