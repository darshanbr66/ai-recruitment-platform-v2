"""Windows compatibility shim.

psycopg3's async mode cannot run on the default Windows `ProactorEventLoop`
(it requires a selector-based loop). This must be called before any asyncio
event loop is created — at the top of `main.py`, `alembic/env.py`, and the
test suite's `conftest.py`. A no-op on every other platform.
"""

import asyncio
import sys


def configure_event_loop_policy() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
