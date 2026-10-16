"""API-side Research ports; source and artifact files remain broker-owned."""

from .access import Capabilities
from .records import Records
from .transport import PrivateClient, lease_json


class RemoteBroker:
    def __init__(self, pool, resources, counter, limits, url, secret, *, client=None):
        self.capabilities = Capabilities(pool, resources)
        self.records = Records(self.capabilities)
        self.counter, self.limits = counter, limits
        self.transport = PrivateClient(url, secret, client=client)
        self.environment_digest = None

    async def ready(self, build_id):
        result = await self.transport.call("/health/ready", maximum=65536)
        if result["build_id"] != build_id:
            raise ValueError("Broker source release differs from API pin")
        expected = {
            k: getattr(self.limits, k)
            for k in ("max_sections_per_read", "max_tokens_per_section", "max_tokens_per_read")
        }
        if result["read_limits"] != expected:
            raise ValueError("Broker read limits differ from the shared tool contract")
        digest = result["environment_digest"]
        if self.environment_digest is not None and digest != self.environment_digest:
            raise ValueError("Runner environment changed")
        self.environment_digest = digest
        return result

    async def call(self, token, operation, arguments, *, request_id):
        return await self.transport.call(
            "/data",
            {
                "token": token,
                "operation": operation,
                "arguments": arguments,
                "request_id": request_id,
            },
            maximum=65536,
        )

    async def artifact_value(self, access, row):
        return await self.transport.call(
            "/artifact", {"lease": lease_json(access.context), "ref": row["ref"]}
        )

    async def retain(self, access, refs):
        await self.transport.call(
            "/retain", {"lease": lease_json(access.context), "refs": list(refs)}
        )

    async def prune(self):
        await self.transport.call("/maintenance", {})

    async def close(self):
        await self.transport.close()


class RemotePython:
    def __init__(self, broker):
        self.broker = broker

    async def execute(
        self, context, code, purpose, input_refs, *, request_id, analysis_provenance=None
    ):
        return await self.broker.transport.call(
            "/python",
            {
                "lease": lease_json(context),
                "code": code,
                "purpose": purpose,
                "input_refs": input_refs,
                "request_id": request_id,
                "analysis_provenance": analysis_provenance,
                "environment_digest": self.broker.environment_digest,
            },
            maximum=65536,
        )
