from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from models.raw_review import RawReview


class CollectorInterface(ABC):
    """Contract every platform connector must satisfy.

    Each collector is stateless between calls — credentials are injected at
    construction time. `fetch` is the only method called by the pipeline.
    """

    @abstractmethod
    def fetch(
        self,
        query: str,
        limit: int,
        since_date: Optional[datetime] = None,
    ) -> list[RawReview]:
        """Return up to `limit` raw reviews published after `since_date`."""
        ...

    @abstractmethod
    def validate_credentials(self) -> bool:
        """Return True if the platform is reachable and credentials (if any) are valid."""
        ...

    @abstractmethod
    def platform_name(self) -> str:
        """Return the canonical platform slug (matches RawReview.source_platform)."""
        ...
