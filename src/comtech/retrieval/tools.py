"""Shared document tool shapes; trusted callers may restrict the eligible document set."""

import asyncio
from copy import deepcopy

from comtech.research.accounting import source_call

from .store import ReadArgs, SearchArgs

DOCUMENT_SCHEMAS = {
    "knowledge_search": {
        "description": "Discover enterprise documents and snippets.",
        "parameters": SearchArgs.model_json_schema(),
    },
    "read_document_sections": {
        "description": "Inspect bounded exact sections within one known document.",
        "parameters": ReadArgs.model_json_schema(),
    },
}


def document_schemas(limits):
    """Advertise the same configured bounds enforced by the shared reader."""
    schemas = deepcopy(DOCUMENT_SCHEMAS)
    args = schemas["read_document_sections"]["parameters"]["properties"]
    args["max_sections"]["maximum"] = limits.max_sections_per_read
    args["max_sections"]["default"] = min(3, limits.max_sections_per_read)
    return schemas


class DocumentTools:
    def __init__(self, store, search, counter, limits):
        self.store, self.search, self.counter, self.limits = store, search, counter, limits

    async def call(self, name, arguments, *, allowed_ids=None):
        if name == "knowledge_search":
            args = SearchArgs.model_validate(arguments)
            if allowed_ids is None:
                return await self.search.search(args)
            return await self.search.search(args, allowed_ids=allowed_ids)
        if name != "read_document_sections":
            raise ValueError("Unknown document tool")
        args = ReadArgs.for_limits(arguments, self.limits)
        args.document_id = self.store.resolve_document_id(args.document_id)
        if allowed_ids is not None and args.document_id not in allowed_ids:
            raise ValueError("Document is outside the assigned scope")
        return await source_call(
            lambda: asyncio.to_thread(self.store.read, args, self.counter, self.limits)
        )
