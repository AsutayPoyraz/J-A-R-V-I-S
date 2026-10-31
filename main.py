"""J.A.R.V.I.S. v11 application entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent
PC_AGENT_ROOT = REPO_ROOT / "platform" / "pc-agent"


def _run_api(host: str | None, port: int | None) -> None:
    """Start the platform PC Agent through Uvicorn."""
    sys.path.insert(0, str(PC_AGENT_ROOT))

    import uvicorn

    from jarvis_agent import config
    from jarvis_agent.app import create_app

    bind_host = host or config.BIND_HOST
    bind_port = port or config.BIND_PORT
    app = create_app()
    uvicorn.run(app, host=bind_host, port=bind_port, log_level="info")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="J.A.R.V.I.S.")
    parser.add_argument(
        "--api",
        action="store_true",
        help="FastAPI PC Agent'i Uvicorn ile başlat",
    )
    parser.add_argument("--host", help="API bind adresi (varsayılan: 127.0.0.1)")
    parser.add_argument("--port", type=int, help="API portu (varsayılan: 8000)")
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Paketlenmiş çalışma zamanı denetimini çalıştır",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.self_test:
        from services.packaging_validation import frozen_runtime_check

        raise SystemExit(0 if frozen_runtime_check() else 1)
    if args.api:
        _run_api(args.host, args.port)
        return

    from jarvis_v11 import main as desktop_main

    desktop_main()


if __name__ == "__main__":
    main()
