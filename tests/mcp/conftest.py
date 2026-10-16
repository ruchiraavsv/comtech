import asyncio
import os
import socket
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
import pytest_asyncio
import uvicorn

pytest.importorskip("mcp", reason="Install the mcp project extra for MCP tests")

from comtech.mcp.repository import load_snapshot
from comtech.mcp.server import create_app
from comtech.mcp.settings import MCPSettings

FIXTURES = Path(__file__).resolve().parents[2] / "synthetic_bank/mcp/fixtures"


@pytest.fixture
def snapshot():
    return load_snapshot(FIXTURES)


@asynccontextmanager
async def serve(app):
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    server = uvicorn.Server(
        uvicorn.Config(
            app, log_level="warning", lifespan="on", access_log=False, timeout_graceful_shutdown=2
        )
    )
    task = asyncio.create_task(server.serve(sockets=[listener]))
    try:
        async with asyncio.timeout(10):
            while not server.started:
                if task.done():
                    await task
                    raise RuntimeError("Test server exited before readiness")
                await asyncio.sleep(0.01)
        yield f"http://127.0.0.1:{listener.getsockname()[1]}"
    finally:
        server.should_exit = True
        await asyncio.wait_for(task, 5)
        listener.close()


@pytest_asyncio.fixture
async def server_url():
    external = os.environ.get("NORTHSTAR_MCP_TEST_URL")
    if external:
        yield external.rstrip("/")
    else:
        async with serve(create_app(MCPSettings(fixture_directory=FIXTURES))) as url:
            yield url
