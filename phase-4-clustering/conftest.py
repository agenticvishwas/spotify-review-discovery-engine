import sys
from pathlib import Path

# Make phase-4 packages importable when running pytest from the phase-4 directory
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "phase-3-ai-analysis"))
sys.path.insert(0, str(Path(__file__).parent.parent / "phase-2-preprocessing"))
