from types import SimpleNamespace

import pytest

from comtech.research.artifacts import json_bytes
from comtech.research.broker_contracts import (
    DOCUMENT_FIELDS,
    OPERATIONS,
    BrokerError,
    DocumentSetSpec,
)
from comtech.research.contracts import SourceScope
from comtech.research.data_sdk import DataError, DataSDK
from comtech.research.documents import Documents
from comtech.retrieval.store import ReadArgs, SearchArgs
from tests.retrieval.test_sources import BUILD, make_release


def test_sdk_uses_shared_argument_shapes_and_exposes_no_management():
    requests = []

    def transport(operation, args):
        requests.append((operation, args))
        return {
            "value": {"observations": [], "details": "synthetic", "error": None},
            "receipt_ref": "REF-synthetic",
        }

    sdk = DataSDK(transport)
    result = sdk.knowledge_search("retry", service_ids=["svc-1"])
    assert SearchArgs.model_validate(requests[-1][1]).top_k == 8
    assert result["observations"] == []
    sdk.read_document_sections("DOC-1", "replication")
    assert ReadArgs.model_validate(requests[-1][1]).max_sections == 3
    assert sdk.receipt_refs == ["REF-synthetic"] * 2
    assert not any(
        hasattr(sdk, name) for name in ("query", "lookup", "grant", "issue", "revoke", "embed")
    )
    with pytest.raises(DataError) as failure:
        DataSDK(
            lambda *args: {"value": {"error": {"code": "SCOPE_DENIED", "message": "Denied"}}}
        ).describe()
    assert failure.value.code == "SCOPE_DENIED"


async def test_version_family_policy_and_effective_unknowns_are_explicit(tmp_path):
    store = make_release(tmp_path, ["Old", "New", "Unrelated"])
    store.documents["DOC-0"].update(
        document_family_id="family", version=1, effective_to="2026-02-01"
    )
    store.documents["DOC-1"].update(
        document_family_id="family", version=2, effective_from="2026-02-01"
    )
    store.documents["DOC-2"]["effective_from"] = None
    scope = SourceScope(
        scope_ref="scope",
        sources=["documents"],
        datasets={"documents": ["documents"]},
        fields={"documents": list(DOCUMENT_FIELDS)},
        capabilities=list(OPERATIONS),
        pinned_versions={"documents": BUILD},
    )

    class Records:
        async def offset(self, *args):
            return 0

        async def put(self, *args, **kwargs):
            return kwargs["ref"]

    documents = Documents(store, Records())
    access = SimpleNamespace(
        scope=scope, context=SimpleNamespace(lease=SimpleNamespace(task_id="synthetic"))
    )
    latest = scope.model_copy(update={"document_version_policy": "latest_in_release"})
    assert [d["document_id"] for d in documents.eligible(latest)] == ["DOC-1", "DOC-2"]
    assert len(documents.eligible(scope)) == 3
    page = await documents.enumerate(access, DocumentSetSpec(effective_at="2026-01-15"))
    assert [r["document_id"] for r in page["items"]] == ["DOC-0"]
    assert page["coverage"]["excluded_unknown_effective_start"] == 1
    assert page["coverage"]["count_unit"] == "document versions"


def test_artifact_input_rejects_executable_and_nonfinite_values():
    for value in ({"code": object()}, {"x": float("inf")}, {1: "not a string key"}):
        with pytest.raises(BrokerError):
            json_bytes(value)
    assert json_bytes({"unknown": None}) == b'{"unknown":null}'
