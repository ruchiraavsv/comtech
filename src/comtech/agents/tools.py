"""Worker tool registry and bounded error boundary."""

import asyncio

from pydantic import ValidationError

from comtech.agents.contracts import ToolFailure, ToolResult
from comtech.mcp.tools import TOOL_SPECS
from comtech.research.accounting import source_call
from comtech.research.ledger import AccountingError
from comtech.retrieval.store import DocumentArgumentError
from comtech.retrieval.tools import DOCUMENT_SCHEMAS, DocumentTools, document_schemas


class KnowledgeTools:
    def __init__(self, store, search, mcp, counter, limits):
        self.store, self.search, self.mcp = store, search, mcp
        self.counter, self.limits = counter, limits
        self.documents = DocumentTools(store, search, counter, limits)
        self.schemas = {
            **document_schemas(limits),
            **{
                name: {"description": spec[2], "parameters": spec[0].model_json_schema()}
                for name, spec in TOOL_SPECS.items()
            },
        }

    def maximum(self, name):
        if name == "read_document_sections":
            return self.limits.max_tokens_per_read
        return 3000

    async def call(self, name, arguments):
        try:
            async with asyncio.timeout(self.limits.tool_timeout_seconds):
                if name in DOCUMENT_SCHEMAS:
                    result = await self.documents.call(name, arguments)
                elif name in TOOL_SPECS:
                    result = await source_call(lambda: self.mcp.call(name, arguments))
                else:
                    raise ValueError("Unknown tool")
            if self.counter.count(result) > self.maximum(name):
                return self.failure(name, "RESULT_TOO_LARGE", "Tool result exceeded its bound.")
            return result
        except AccountingError:
            raise
        except DocumentArgumentError as error:
            return self.failure(name, "INVALID_ARGUMENT", str(error))
        except (ValueError, ValidationError):
            return self.failure(name, "INVALID_ARGUMENT", "Arguments or source contract invalid.")
        except KeyError:
            return self.failure(name, "NOT_FOUND", "Requested source was not found.")
        except TimeoutError:
            return self.failure(name, "TIMEOUT", "Tool deadline expired.")
        except Exception:
            return self.failure(name, "UNAVAILABLE", "Source unavailable; no replacement facts.")

    @staticmethod
    def failure(name, code, message):
        return ToolResult(error=ToolFailure(tool_name=name, code=code, message=message))
