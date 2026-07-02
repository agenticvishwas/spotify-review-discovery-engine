"""Launch the Phase 7 Streamlit dashboard.

Usage:
    python run_dashboard.py [--port 8501] [--db-path /path/to/knowledge_base.db]
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

_PHASE7_ROOT = Path(__file__).parent


def main() -> None:
    parser = argparse.ArgumentParser(description="Launch Phase 7 Streamlit dashboard")
    parser.add_argument("--port", type=int, default=8501)
    parser.add_argument("--db-path", default=None, help="Override DB path")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    app_path = _PHASE7_ROOT / "dashboards" / "app.py"

    if args.db_path:
        os.environ["DB_PATH"] = args.db_path

    cmd = [
        sys.executable, "-m", "streamlit", "run", str(app_path),
        "--server.port", str(args.port),
        "--server.headless", "true" if args.no_browser else "false",
        "--theme.base", "light",
    ]
    print(f"Launching dashboard at http://localhost:{args.port}")
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
