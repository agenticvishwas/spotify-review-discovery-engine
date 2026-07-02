from __future__ import annotations
import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterator

logger = logging.getLogger(__name__)


class BaseLoader(ABC):
    def __init__(self, data_dir: str):
        self._data_dir = Path(data_dir)

    def _iter_jsonl(self, glob: str = "**/*.jsonl") -> Iterator[dict]:
        if not self._data_dir.exists():
            logger.warning("Data dir missing: %s", self._data_dir)
            return
        for path in sorted(self._data_dir.glob(glob)):
            # Skip excluded / failed / manifest files
            if any(tag in path.name for tag in (".excluded", ".failed", ".errors", "manifest")):
                continue
            yield from self._read_file(path)

    def _read_file(self, path: Path) -> Iterator[dict]:
        try:
            with path.open("r", encoding="utf-8") as fh:
                for lineno, line in enumerate(fh, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError as exc:
                        logger.warning("Bad JSONL %s:%d — %s", path, lineno, exc)
        except OSError as exc:
            logger.error("Cannot read %s — %s", path, exc)

    @abstractmethod
    def load_all(self) -> tuple[list[dict], int]:
        """Return (records_for_db, skipped_count)."""
