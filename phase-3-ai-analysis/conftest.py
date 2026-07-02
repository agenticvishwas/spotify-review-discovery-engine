"""pytest configuration — adds phase-3-ai-analysis root and phase-2-preprocessing to sys.path."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "phase-2-preprocessing"))
