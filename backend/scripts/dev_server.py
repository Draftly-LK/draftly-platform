"""Development server entrypoint.

Exists because of a Windows-only ordering problem. ``uvicorn.Server.run`` calls
``asyncio.run`` *before* it imports the application, so a policy set inside
``src/main.py`` arrives after the loop already exists. psycopg's async driver
then fails every connection with::

    InterfaceError: Psycopg cannot use the 'ProactorEventLoop' to run in async mode

Setting the policy here — before uvicorn is imported — means the loop uvicorn
creates is a selector loop. On Linux and macOS this module is a thin passthrough
and changes nothing, so production entrypoints may keep calling uvicorn directly.

Usage::

    uv run python scripts/dev_server.py --port 8000 --reload
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Running this file directly puts scripts/ on sys.path rather than the backend
# root, so "src" would not import. Prepending the backend root keeps the script
# runnable as both `python scripts/dev_server.py` and `python -m scripts.dev_server`.
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

import uvicorn  # noqa: E402  — must follow the event-loop policy above


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Draftly API dev server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    # uvicorn >= 0.36 passes an explicit loop_factory to asyncio.run, which
    # ignores the event-loop policy set above. `loop` also accepts an import
    # string used directly as that factory, so name the selector loop for it.
    loop: str = "asyncio:SelectorEventLoop" if sys.platform == "win32" else "auto"

    uvicorn.run("src.main:app", host=args.host, port=args.port, reload=args.reload, loop=loop)


if __name__ == "__main__":
    main()
