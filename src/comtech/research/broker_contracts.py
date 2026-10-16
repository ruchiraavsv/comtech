"""Bounded document-only broker requests. Shared tools keep their existing schemas."""

from typing import Literal

from pydantic import Field, model_validator

from .contracts import AnalysisProcess, Versioned

MAX_PAGE_BYTES = 64 * 1024
MAX_ARTIFACT_BYTES = 32 * 1024 * 1024
DOCUMENT_FIELDS = (
    "document_id",
    "document_family_id",
    "version",
    "title",
    "document_type",
    "department",
    "service_ids",
    "created_at",
    "effective_from",
    "effective_to",
    "supersedes_document_id",
    "classification",
    "source_sha256",
)
OPERATIONS = (
    "describe",
    "knowledge_search",
    "read_document_sections",
    "enumerate_documents",
    "read_spans",
    "read_artifact",
    "write_artifact",
)

# Python sees reply.value directly (no transport envelope). Keep nesting explicit at
# the decision point; request schemas alone do not explain how to consume results.
SDK_RESULT_GUIDE = {
    "describe": {
        "total_count": "int: scoped published document versions",
        "population_hash": "str",
        "fields": "list[str]",
    },
    "enumerate_documents": {
        "items": "list[requested metadata fields plus document_ref]",
        "next_cursor": "str|null; pass unchanged as cursor with the same filters/fields",
        "truncated": "bool: more pages remain",
        "coverage": {
            "total_count": "int: full filtered population, NOT a top-level field",
            "returned_count": "int: this page",
            "enumerated_through": "int: exclusive end offset",
            "population_hash": "str: must match across pages",
        },
    },
    "read_document_sections": {
        "observations": [
            {
                "observation_id": "str: registered inspected-span reference",
                "title": "str: section heading",
                "content": "str: exact inspected source text",
                "source_ref": {
                    "source_id": "str: document ID",
                    "section_id": "str: exact section ID",
                },
            }
        ],
        "section_options": "uninspected section_id/title navigation metadata",
        "section_options_truncated": "bool: directory is incomplete",
        "omitted_sections": "bool: not all content inspected",
    },
    "read_artifact": {
        "items": "list: paged result rows; a JSON object is one row",
        "total_count": "int: result rows",
        "next_cursor": "str|null",
        "truncated": "bool",
    },
    "write_artifact": {
        "artifact_ref": "str: select as computation_ref",
        "coverage": "registered input coverage",
    },
}


class BrokerError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


class DescribeArgs(Versioned):
    source: str = "documents"
    dataset: str | None = None


class DocumentSetSpec(Versioned):
    document_types: list[str] | None = Field(default=None, max_length=30)
    departments: list[str] | None = Field(default=None, max_length=30)
    service_ids: list[str] | None = Field(default=None, max_length=100)
    document_ids: list[str] | None = Field(default=None, max_length=1000)
    fields: list[str] = Field(default_factory=lambda: list(DOCUMENT_FIELDS), max_length=30)
    version_policy: Literal["pinned", "latest_in_release", "all_in_release"] = "pinned"
    effective_at: str | None = Field(default=None, max_length=40)
    limit: int = Field(default=100, ge=1, le=1000)
    cursor: str | None = Field(default=None, max_length=100)


class SpanRequest(Versioned):
    document_ref: str = Field(min_length=1, max_length=100)
    section_id: str | None = Field(default=None, max_length=200)
    char_start: int = Field(default=0, ge=0)
    char_end: int | None = Field(default=None, ge=1)
    max_chars: int = Field(default=4000, ge=1, le=8000)
    cursor: str | None = Field(default=None, max_length=100)


class ReadArtifactArgs(Versioned):
    artifact_ref: str = Field(min_length=1, max_length=100)
    limit: int = Field(default=100, ge=1, le=1000)
    cursor: str | None = Field(default=None, max_length=100)


class WriteArtifactArgs(Versioned):
    value: dict | list
    format: Literal["json", "parquet"] = "json"
    input_refs: list[str] = Field(min_length=1, max_length=1000)
    method: str = Field(min_length=1, max_length=1000)
    units: str | None = Field(default=None, max_length=100)
    assumptions: list[str] = Field(default_factory=list, max_length=30)
    extraction_version: str | None = Field(default=None, max_length=100)
    analysis_process: AnalysisProcess | None = None

    @model_validator(mode="after")
    def table(self):
        if self.format == "parquet" and (
            not isinstance(self.value, list) or any(not isinstance(r, dict) for r in self.value)
        ):
            raise ValueError("Parquet requires a list of typed row objects")
        return self
