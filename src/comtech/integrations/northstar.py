"""Application MCP client. Independent connections avoid shared request state."""

import asyncio

from mcp import Client

from comtech.agents.budget import serialized
from comtech.agents.contracts import SourceRef, ToolFailure, ToolResult
from comtech.mcp.models import Response
from comtech.mcp.tools import TOOL_SPECS
from comtech.retrieval.store import observation

SOURCE_TYPES = {
    "employees": "employee_directory",
    "services": "service_catalog",
    "open_incidents": "incident_record",
    "oncall_shifts": "oncall_shift",
    "deployments": "deployment",
}


class NorthstarClient:
    def __init__(self, url, timeout=15):
        self.url, self.timeout = url, timeout

    async def discover(self):
        async with asyncio.timeout(self.timeout), Client(self.url) as client:
            listing = await client.list_tools()
            found = {t.name: t for t in listing.tools}
            if set(found) != set(TOOL_SPECS):
                raise ValueError("MCP tool inventory differs from expected contract")
            for name, (args, output, _) in TOOL_SPECS.items():
                tool = found[name]
                if (
                    tool.input_schema != args.model_json_schema()
                    or tool.output_schema != Response[output].model_json_schema()
                ):
                    raise ValueError("MCP discovery schema mismatch")

    async def call(self, name, arguments):
        args, output, _ = TOOL_SPECS[name]
        validated = args.model_validate(arguments)
        async with asyncio.timeout(self.timeout), Client(self.url) as client:
            result = await client.call_tool(name, validated.model_dump(exclude_none=True))
        data = result.structured_content
        if result.is_error:
            error = data.get("error", {}) if isinstance(data, dict) else {}
            return ToolResult(
                error=ToolFailure(
                    tool_name=name,
                    code=error.get("code", "UNAVAILABLE"),
                    message=error.get("message", "MCP could not complete this request."),
                )
            )
        body = Response[output].model_validate(data).model_dump(mode="json")
        from comtech.research.accounting import CURRENT

        context = CURRENT.get()
        if context:
            objective = await context.ledger.check(context.lease)
            if body["snapshot_id"] != objective["pinned_versions"].get("northstar"):
                raise ValueError("MCP snapshot differs from the pinned objective")
        source = body["source"].removeprefix("northstar:")
        if source not in SOURCE_TYPES:
            raise ValueError("Unexpected MCP source")
        payload = body["payload"]
        return ToolResult(
            observations=[
                observation(
                    SourceRef(
                        source_type=SOURCE_TYPES[source],
                        source_id=body["source"],
                        version=body["snapshot_id"],
                        record_id=body["record_id"],
                    ),
                    name,
                    # Query scope is evidence too, especially for an empty list. Include
                    # the validated request in hashed content so materialization/review
                    # retain it and identical results from different filters cannot merge.
                    serialized(
                        {
                            **payload,
                            "_query": {
                                "tool": name,
                                "arguments": validated.model_dump(mode="json"),
                            },
                        }
                    ),
                    as_of=body["as_of"],
                    updated_at=payload.get("updated_at"),
                )
            ],
            details="Operational snapshot; symptoms are not confirmed root causes.",
        )
