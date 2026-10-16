"""Independent ASGI service using the official MCP SDK's protocol/HTTP transport."""

import asyncio
import json
import logging
from contextlib import asynccontextmanager

import mcp_types as types
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from .repository import load_snapshot
from .settings import MCPSettings
from .tools import ToolService, tool_definitions

LOGGER = logging.getLogger("comtech.mcp")


def create_app(settings=None, *, service_factory=ToolService):
    settings = settings or MCPSettings()

    async def list_tools(context, params):
        return types.ListToolsResult(tools=tool_definitions())

    async def call_tool(context, params):
        return await app.state.tool_service.call(params.name, params.arguments, context.request_id)

    protocol = Server(
        "northstar-bank",
        version="1.0.0",
        on_list_tools=list_tools,
        on_call_tool=call_tool,
        instructions="Read-only fictional bank snapshot at 2026-09-15T10:00:00Z. Symptoms are not "
        "confirmed causes. Historical explanations are in documents.",
    )
    manager = StreamableHTTPSessionManager(
        protocol,
        stateless=True,
        json_response=True,
        max_request_body_size=65536,
        security_settings=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=settings.allowed_hosts,
            allowed_origins=settings.allowed_origins,
        ),
    )

    @asynccontextmanager
    async def lifespan(app):
        app.state.ready = False
        try:
            snapshot = await asyncio.to_thread(load_snapshot, settings.fixture_directory)
        except Exception as exc:
            LOGGER.error(
                json.dumps(
                    {
                        "event": "mcp_startup_failed",
                        "error_type": type(exc).__name__,
                        "reason": str(exc),
                    }
                )
            )
            raise
        app.state.tool_service = service_factory(
            snapshot, timeout_seconds=settings.lookup_timeout_seconds
        )
        async with manager.run():
            app.state.ready = True
            LOGGER.info(json.dumps({"event": "mcp_ready", **snapshot.info()}))
            try:
                yield
            finally:
                app.state.ready = False
                LOGGER.info(json.dumps({"event": "mcp_stopping"}))

    async def live(request):
        return JSONResponse({"status": "live"})

    async def ready(request):
        if not app.state.ready:
            return JSONResponse({"status": "not_ready"}, status_code=503)
        return JSONResponse({"status": "ready", **app.state.tool_service.snapshot.info()})

    class MCPTransport:
        async def __call__(self, scope, receive, send):
            if scope["path"].rstrip("/") != "/mcp":
                await JSONResponse({"error": "Not found"}, status_code=404)(scope, receive, send)
                return
            await manager.handle_request(scope, receive, send)

    app = Starlette(
        routes=[
            Route("/health/live", live),
            Route("/health/ready", ready),
            Mount("/", app=MCPTransport()),
        ],
        lifespan=lifespan,
    )
    app.state.ready = False
    return app
