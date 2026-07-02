"""pytest configuration — adds phase-1-data-ingestion root to sys.path so
absolute imports (from models.raw_review import ...) work when running
`pytest` from this directory."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
