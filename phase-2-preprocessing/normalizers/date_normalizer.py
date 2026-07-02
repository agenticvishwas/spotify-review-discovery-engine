import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class DateNormalizer:
    """Parse and normalize timestamps to UTC ISO8601.

    Returns the original string unchanged if parsing fails, ensuring
    the lineage field is never silently lost.
    """

    def normalize(self, date_str: str) -> str:
        if not date_str:
            return date_str

        # Replace Z suffix — not handled by strptime %z before Python 3.11
        cleaned = date_str.strip().replace("Z", "+00:00")

        # Try fromisoformat first (handles most ISO8601 variants in Python 3.11+)
        try:
            dt = datetime.fromisoformat(cleaned)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat()
        except (ValueError, TypeError):
            pass

        # Fallback for common formats without timezone
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(cleaned, fmt).replace(tzinfo=timezone.utc)
                return dt.isoformat()
            except ValueError:
                continue

        logger.debug("DateNormalizer could not parse: %r", date_str)
        return date_str
