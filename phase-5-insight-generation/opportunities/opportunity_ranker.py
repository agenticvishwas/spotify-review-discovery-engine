"""Final opportunity ranking and filtering.

Applies three sorting passes:
  1. Primary sort: opportunity_score descending
  2. Secondary sort: frequency_score descending (breaks ties)
  3. Confidence filter: insights with review_required=True are separated into
     a "pending_review" bucket so the PM's main feed stays high-signal.

No LLM call — purely deterministic.
"""

import logging
from dataclasses import dataclass

from schemas.product_insight import ProductInsight

logger = logging.getLogger(__name__)


@dataclass
class RankedInsights:
    main_feed: list[ProductInsight]        # confidence >= threshold, sorted by opp_score
    pending_review: list[ProductInsight]   # review_required=True, sorted by opp_score
    all_ranked: list[ProductInsight]       # full combined list (main_feed first)


class OpportunityRanker:
    """Sorts and partitions ProductInsight objects for PM consumption."""

    def rank(self, insights: list[ProductInsight]) -> RankedInsights:
        """Sort and partition insights.

        Returns a RankedInsights with:
          - main_feed: high-confidence insights sorted by opportunity_score
          - pending_review: low-confidence insights sorted by opportunity_score
          - all_ranked: main_feed + pending_review (for storage)
        """
        main: list[ProductInsight] = []
        pending: list[ProductInsight] = []

        for insight in insights:
            if insight.review_required:
                pending.append(insight)
            else:
                main.append(insight)

        def sort_key(ins: ProductInsight) -> tuple:
            return (-ins.opportunity_score, -ins.frequency_score)

        main.sort(key=sort_key)
        pending.sort(key=sort_key)

        all_ranked = main + pending

        logger.info(
            "ranker=complete main_feed=%d pending_review=%d",
            len(main), len(pending),
        )
        if main:
            logger.info(
                "ranker=top_insight title=%r opp_score=%.3f",
                main[0].title, main[0].opportunity_score,
            )

        return RankedInsights(
            main_feed=main,
            pending_review=pending,
            all_ranked=all_ranked,
        )
