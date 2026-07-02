"""pytest configuration — adds phase-2-preprocessing root to sys.path so
absolute imports (from models.normalized_review import ...) work when running
`pytest` from this directory."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
