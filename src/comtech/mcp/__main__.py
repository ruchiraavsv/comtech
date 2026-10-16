"""Run only the MCP service."""

import logging

import uvicorn

from .server import create_app
from .settings import MCPSettings


def main():
    settings = MCPSettings()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    uvicorn.run(
        create_app(settings),
        host=settings.host,
        port=settings.port,
        access_log=False,
        timeout_graceful_shutdown=10,
    )


if __name__ == "__main__":
    main()
