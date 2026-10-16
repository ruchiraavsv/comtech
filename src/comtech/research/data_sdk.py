"""Python-facing data API. A runner supplies only an execution-scoped JSON transport.

This module deliberately has no provider clients, credentials, URLs, filesystem or
management operations. Transport/isolation wiring is supplied by the R4 runner.
"""


class DataError(RuntimeError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


class DataSDK:
    def __init__(self, request):
        self._request = request
        self.receipt_refs = []

    def _call(self, operation, arguments):
        reply = self._request(operation, arguments)
        value = reply["value"]
        if value.get("error"):
            error = value["error"]
            raise DataError(error["code"], error["message"])
        if reply.get("receipt_ref"):
            self.receipt_refs.append(reply["receipt_ref"])
        return value

    def describe(self, source="documents", dataset=None):
        return self._call("describe", {"source": source, "dataset": dataset})

    def knowledge_search(
        self,
        query,
        document_types=None,
        departments=None,
        service_ids=None,
        created_after=None,
        created_before=None,
        top_k=8,
    ):
        return self._call(
            "knowledge_search",
            {
                "query": query,
                "document_types": document_types,
                "departments": departments,
                "service_ids": service_ids,
                "created_after": created_after,
                "created_before": created_before,
                "top_k": top_k,
            },
        )

    def read_document_sections(self, document_id, query, section_ids=None, max_sections=3):
        return self._call(
            "read_document_sections",
            {
                "document_id": document_id,
                "query": query,
                "section_ids": section_ids,
                "max_sections": max_sections,
            },
        )

    def enumerate_documents(self, spec=None):
        return self._call("enumerate_documents", spec or {})

    def read_spans(self, document_ref, span_request=None):
        return self._call("read_spans", {**(span_request or {}), "document_ref": document_ref})

    def read_artifact(self, artifact_ref, *, limit=100, cursor=None):
        return self._call(
            "read_artifact",
            {
                "artifact_ref": artifact_ref,
                "limit": limit,
                "cursor": cursor,
            },
        )

    def write_artifact(
        self,
        value,
        format,
        input_refs,
        *,
        method,
        units=None,
        assumptions=None,
        extraction_version=None,
        analysis_process=None,
    ):
        return self._call(
            "write_artifact",
            {
                "value": value,
                "format": format,
                "input_refs": input_refs,
                "method": method,
                "units": units,
                "assumptions": assumptions or [],
                "extraction_version": extraction_version,
                "analysis_process": analysis_process,
            },
        )
