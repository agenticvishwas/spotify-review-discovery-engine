"""Launch the Phase 7 FastAPI server.

Usage:
    python run_api.py [--port 8000] [--db-path /path/to/knowledge_base.db]
"""
import argparse
import os
import sys
from pathlib import Path

_PHASE7_ROOT = Path(__file__).parent
if str(_PHASE7_ROOT) not in sys.path:
    sys.path.insert(0, str(_PHASE7_ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(description="Launch Phase 7 FastAPI server")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--db-path", default=None, help="Override DB path")
    parser.add_argument("--reload", action="store_true", help="Dev auto-reload")
    args = parser.parse_args()

    if args.db_path:
        os.environ["DB_PATH"] = args.db_path

    import uvicorn
    uvicorn.run("api.routes:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()