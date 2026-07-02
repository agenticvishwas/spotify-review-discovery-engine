"""Append-only JSONL writer/reader for Phase 4 ReviewCluster output.

Storage layout:
    {base_dir}/{YYYY-MM-DD}/{batch_id}.jsonl
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union

from cluster_models.review_cluster import ReviewCluster

logger = logging.getLogger(__name__)

DEFAULT_CLUSTER_DIR = Path("data") / "clusters"


class ClusterStore:
    def __init__(self, base_dir: Union[str, Path] = DEFAULT_CLUSTER_DIR):
        self._base_dir = Path(base_dir)

    # ── Write ────────────────────────────────────────────────────────────────

    def write_batch(
        self,
        clusters: list[ReviewCluster],
        batch_id: str,
        date_str: Optional[str] = None,
    ) -> Path:
        path = self._batch_path(batch_id, date_str)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            for cluster in clusters:
                fh.write(cluster.to_jsonl() + "\n")
        logger.info(
            "phase=4 action=write_clusters batch=%s records=%d path=%s",
            batch_id, len(clusters), path,
        )
        return path

    def append(
        self,
        cluster: ReviewCluster,
        batch_id: str,
        date_str: Optional[str] = None,
    ) -> None:
        path = self._batch_path(batch_id, date_str)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(cluster.to_jsonl() + "\n")

    # ── Read ─────────────────────────────────────────────────────────────────

    def list_all(self, date_str: Optional[str] = None) -> list[ReviewCluster]:
        """Read all clusters written for a given date."""
        date = date_str or self._today()
        date_dir = self._base_dir / date
        if not date_dir.exists():
            return []
        clusters: list[ReviewCluster] = []
        for path in sorted(date_dir.glob("*.jsonl")):
            clusters.extend(self._read_jsonl(path))
        return clusters

    def _read_jsonl(self, path: Path) -> list[ReviewCluster]:
        clusters: list[ReviewCluster] = []
        with path.open("r", encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    clusters.append(ReviewCluster.model_validate_json(line))
                except Exception as exc:
                    logger.warning("Skipping malformed JSONL at %s:%d — %s", path, lineno, exc)
        return clusters

    # ── Path helpers ─────────────────────────────────────────────────────────

    def _today(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _batch_path(self, batch_id: str, date_str: Optional[str] = None) -> Path:
        return self._base_dir / (date_str or self._today()) / f"{batch_id}.jsonl"
