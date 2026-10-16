import pytest

from comtech.agents.budget import digest
from comtech.agents.contracts import (
    AnswerClaim,
    ClaimEvidenceLink,
    EvidenceRecord,
    FinalDraft,
    RenderedParagraph,
    SourceRef,
    SupervisorAnswerPackage,
    SupportedClaim,
)
from comtech.agents.evidence import validate_package
from comtech.agents.graph import render
from comtech.research.contracts import (
    AnalysisArtifact,
    AnalysisProcess,
    Coverage,
    ExecutionRecord,
    ExtendedWorkerResult,
    QueryRecord,
    RegisteredClaim,
)
from comtech.research.evidence import EvidenceRegistry


def fixture():
    registry = EvidenceRegistry("run", "obj", {"root": None, "child": "root"})
    evidence = EvidenceRecord(
        evidence_id="EV-source",
        observation_id="obs",
        run_id="run",
        task_id="child",
        source_ref=SourceRef(
            source_type="document",
            source_id="synthetic",
            version="v1",
            section_id="s1",
            char_start=0,
            char_end=9,
        ),
        title="Synthetic measurement",
        content="Value: 2.",
        content_hash=digest("Value: 2."),
        retrieved_at="2026-09-30T00:00:00Z",
        as_of="2026-09-15T00:00:00Z",
    )
    registry.evidence[evidence.evidence_id] = evidence
    premise = SupportedClaim(
        claim_id="obj/child/premise",
        statement="The value is 2.",
        support="direct",
        evidence=[ClaimEvidenceLink(evidence_id="EV-source", role="support")],
    )
    derived = SupportedClaim(
        claim_id="obj/root/result",
        statement="Twice the value is 4.",
        support="derived",
        evidence=[ClaimEvidenceLink(evidence_id="EV-source", role="support")],
        premise_claim_ids=[premise.claim_id],
        derivation="Multiply the observed value by 2.",
    )
    for task, claim in (("child", premise), ("root", derived)):
        registry.claims[claim.claim_id] = RegisteredClaim(
            run_id="run",
            objective_id="obj",
            task_id=task,
            claim=claim,
        )
    result = ExtendedWorkerResult(
        task_id="root",
        status="answered",
        termination_reason="completed",
        claims=[derived],
        unresolved=[],
        source_conflicts=[],
        clarification=None,
        tool_failures=[],
    )
    return registry, result


def package(claim, evidence_ids):
    return SupervisorAnswerPackage(
        resolved_request="Double it",
        claims=[
            AnswerClaim(
                claim_id=claim.claim_id,
                statement=claim.statement,
                support=claim.support,
                evidence_ids=evidence_ids,
                premise_claim_ids=claim.premise_claim_ids,
                derivation=claim.derivation,
                computation_ref=claim.computation_ref,
                source_task_ids=["root"],
            )
        ],
        unresolved=[],
        limitations=[],
        source_conflicts=[],
        clarification=None,
    )


def test_export_preserves_child_source_and_transitive_claims():
    registry, result = fixture()
    exported = registry.export(result)
    assert len(exported.result.claims) == 2
    assert exported.evidence["EV-source"] == registry.evidence["EV-source"]
    assert exported.evidence["EV-source"].task_id == "child"
    assert exported.inheritance[0].originating_task_id == "child"
    validate_package(
        package(result.claims[0], ["EV-source"]), {"root": exported}, exported.evidence, registry
    )
    changed = exported.model_copy(deep=True)
    changed.evidence["EV-source"].task_id = "root"
    with pytest.raises(ValueError, match="inheritance"):
        registry.validate_export(changed)
    exported.result.claims[0].statement = "Mutated after export"
    assert registry.claims["obj/child/premise"].claim.statement == "The value is 2."
    with pytest.raises(ValueError, match="changed"):
        registry.validate_export(exported)


@pytest.mark.parametrize("defect", ["missing", "hash", "cycle", "owner", "identity", "forged"])
def test_export_rejects_invalid_lineage(defect):
    registry, result = fixture()
    if defect == "missing":
        registry.claims.pop("obj/child/premise")
    elif defect == "hash":
        registry.evidence["EV-source"].content = "uninspected text"
    elif defect == "cycle":
        registry.claims["obj/child/premise"].claim.premise_claim_ids = ["obj/root/result"]
    elif defect == "owner":
        registry.evidence["EV-source"].run_id = "another-run"
    elif defect == "identity":
        registry.claims["obj/child/premise"].task_id = "root"
    else:
        result = result.model_copy(deep=True)
        result.claims[0].statement = "Forged"
    with pytest.raises(ValueError):
        registry.export(result)


def computation_fixture():
    registry, result = fixture()
    common = dict(run_id="run", objective_id="obj", task_id="child")
    registry.coverage["cov"] = Coverage(
        coverage_ref="cov",
        requested_scope_ref="scope",
        inspected_refs=["EV-source"],
    )
    registry.executions["exec"] = ExecutionRecord(
        **common,
        execution_ref="exec",
        code_hash=digest("2*2"),
        environment_digest="sha256:image",
        input_refs=["EV-source"],
        output_refs=["artifact"],
        started_at="2026-09-30T00:00:00Z",
        finished_at="2026-09-30T00:00:01Z",
        limits={"seconds": 2},
    )
    registry.artifacts["artifact"] = AnalysisArtifact(
        **common,
        artifact_ref="artifact",
        execution_ref="exec",
        method="Multiply by two",
        input_refs=["EV-source"],
        result_ref="payload",
        result_hash=digest("4"),
        units="items",
        assumptions=[],
        coverage_ref="cov",
    )
    registry.payloads["payload"] = "4"
    claim = result.claims[0].model_copy(
        update={
            "evidence": [],
            "premise_claim_ids": [],
            "computation_ref": "artifact",
        }
    )
    registry.claims[claim.claim_id].claim = claim
    return registry, result.model_copy(update={"claims": [claim]})


def test_computed_claim_needs_no_invented_premise_and_renders_registered_lineage():
    registry, result = computation_fixture()
    exported = registry.export(result)
    answer = package(result.claims[0], [])
    validate_package(answer, {"root": exported}, exported.evidence, registry)
    text = render(
        FinalDraft(
            paragraphs=[
                RenderedParagraph(
                    text=result.claims[0].statement,
                    claim_ids=[result.claims[0].claim_id],
                )
            ]
        ),
        answer,
        exported.evidence,
        registry,
    )
    assert "execution exec" in text and "synthetic" in text and digest("4") in text
    assert "version v1" in text and "as of 2026-09-15" in text
    assert "1 registered inputs" in text
    assert "s1 (characters 0–9)" in text
    assert registry.artifacts["artifact"].input_refs == ["EV-source"]
    with pytest.raises(ValueError, match="registry"):
        validate_package(answer, {"root": exported}, exported.evidence)


@pytest.mark.parametrize("defect", ["input", "output", "result", "execution", "cycle"])
def test_computation_rejects_invalid_inputs_or_results(defect):
    registry, result = computation_fixture()
    if defect == "input":
        registry.executions["exec"].input_refs = ["forged"]
    elif defect == "output":
        registry.executions["exec"].output_refs = []
    elif defect == "result":
        registry.payloads["payload"] = "5"
    elif defect == "execution":
        registry.executions.clear()
    else:
        registry.executions["exec"].input_refs = ["artifact"]
        registry.artifacts["artifact"].input_refs = ["artifact"]
    with pytest.raises(ValueError):
        registry.export(result)


def test_process_prose_cannot_replace_computation_result_or_execution():
    from comtech.agents.budget import TokenCounter

    registry, result = computation_fixture()
    registry.artifacts["artifact"].analysis_process = AnalysisProcess(
        summary="Multiplied the observed value by two.",
        population="One inspected measurement, not the full population.",
        checks=["2 times 2 is 4."],
        limitations=["No population coverage established."],
    )
    review = registry.review_computations(TokenCounter())["artifact"]
    assert review["manifest"]["analysis_process"]["summary"].startswith("Multiplied")
    assert review["execution"]["code_hash"] == digest("2*2")
    assert review["result"] == "4" and not review["result_omitted"]
    registry.payloads["payload"] = "5"
    with pytest.raises(ValueError, match="hash mismatch"):
        registry.export(result)
    registry.payloads["payload"] = "4"
    registry.executions.clear()
    with pytest.raises(ValueError, match="Missing registered execution"):
        registry.export(result)


def test_registered_aggregate_can_support_a_claim_without_loading_every_row():
    registry, result = computation_fixture()
    registry.coverage["aggregate"] = Coverage(
        coverage_ref="aggregate",
        requested_scope_ref="scope",
        inspected_refs=[],
        method="aggregate",
        population_definition="Selected synthetic records",
        pinned_versions={"test": "snapshot"},
    )
    registry.queries["query"] = QueryRecord(
        query_ref="query",
        run_id="run",
        objective_id="obj",
        task_id="child",
        source_id="test",
        snapshot="snapshot",
        normalized_query='{"aggregate":"count"}',
        selected_fields=["count"],
        coverage_ref="aggregate",
        result_ref="payload",
        result_hash=digest("4"),
    )
    registry.claims["obj/root/result"].claim.computation_ref = "query"
    exported = registry.export(result)
    assert not exported.evidence
    validate_package(package(result.claims[0], []), {"root": exported}, {}, registry)
    assert "snapshot snapshot" in registry.citation("query", "root")


def test_partial_span_json_roundtrip_is_equal_but_changed_evidence_is_rejected():
    registry, result = fixture()
    registry.evidence["EV-source"].remaining_spans = [(0, 8000), (16000, 23087)]
    envelope = registry.export(result)
    evidence = {k: v.model_dump(mode="json") for k, v in envelope.evidence.items()}
    answer = package(result.claims[0], ["EV-source"])
    validate_package(answer, {"root": envelope}, evidence, registry)
    evidence["EV-source"]["remaining_spans"][0][1] = 7999
    with pytest.raises(ValueError, match="changed after export"):
        validate_package(answer, {"root": envelope}, evidence, registry)


def test_sibling_contributor_does_not_have_to_own_followup_computation():
    registry, result = computation_fixture()
    registry.parents["earlier"] = None
    earlier = registry.export(result.model_copy(update={"task_id": "earlier", "claims": []}))
    envelope = registry.export(result)
    answer = package(result.claims[0], [])
    answer.claims[0].source_task_ids = ["earlier", "root"]
    plan = validate_package(
        answer, {"root": envelope, "earlier": earlier}, envelope.evidence, registry
    )
    assert plan[result.claims[0].claim_id][0]["authorized_root"] == "root"
    draft = FinalDraft(
        paragraphs=[
            RenderedParagraph(text="Twice the value is 4.", claim_ids=[result.claims[0].claim_id])
        ]
    )
    assert render(draft, answer, envelope.evidence, registry) == render(
        draft, answer, envelope.evidence, registry, plan
    )
    answer.claims[0].source_task_ids = ["earlier"]
    with pytest.raises(ValueError, match="does not belong"):
        validate_package(
            answer, {"root": envelope, "earlier": earlier}, envelope.evidence, registry
        )


@pytest.mark.parametrize(
    "defect",
    [
        None,
        "missing_input_grant",
        "missing_artifact_grant",
        "cross_run",
        "cross_objective",
        "hash",
        "execution_owner",
    ],
)
def test_sibling_artifact_grants_preserve_origin_and_validate_complete_lineage(defect):
    registry, result = computation_fixture()
    registry.parents["child"] = None  # Sibling, not descendant of exporting root.
    registry.grants["root"] = {"artifact", "EV-source"}
    if defect == "missing_input_grant":
        registry.grants["root"].remove("EV-source")
    elif defect == "missing_artifact_grant":
        registry.grants["root"].remove("artifact")
    elif defect == "cross_run":
        registry.artifacts["artifact"].run_id = "other"
    elif defect == "cross_objective":
        registry.artifacts["artifact"].objective_id = "other"
    elif defect == "hash":
        registry.payloads["payload"] = "5"
    elif defect == "execution_owner":
        registry.executions["exec"].task_id = "root"
    if defect:
        with pytest.raises(ValueError):
            registry.export(result)
    else:
        envelope = registry.export(result)
        assert envelope.evidence["EV-source"].task_id == "child"
        assert registry.artifacts["artifact"].task_id == "child"
        registry.grants["root"] = {"artifact"}
        with pytest.raises(ValueError, match="inheritance"):
            registry.lineage("EV-source", "root")


def test_enumeration_is_rendered_from_computation_lineage_and_typed_selection():
    from comtech.agents.contracts import CitationSelection

    registry, result = computation_fixture()
    registry.coverage["enum-cov"] = Coverage(
        coverage_ref="enum-cov",
        requested_scope_ref="scope",
        inspected_refs=[],
        method="enumeration",
        total_count=132,
        returned_count=132,
        population_complete=True,
    )
    registry.queries["REF-enumeration"] = QueryRecord(
        query_ref="REF-enumeration",
        run_id="run",
        objective_id="obj",
        task_id="child",
        source_id="documents",
        snapshot="pinned",
        normalized_query="enumerate",
        selected_fields=["created_at"],
        coverage_ref="enum-cov",
        result_ref="enum-result",
        result_hash=digest("132"),
    )
    registry.payloads["enum-result"] = "132"
    registry.artifacts["artifact"].input_refs.append("REF-enumeration")
    registry.executions["exec"].input_refs.append("REF-enumeration")
    envelope = registry.export(result)
    answer = package(result.claims[0], [])
    plan = validate_package(answer, {"root": envelope}, envelope.evidence, registry)
    assert {c["kind"] for c in plan[result.claims[0].claim_id]} == {"computation", "enumeration"}
    draft = FinalDraft(
        paragraphs=[{"text": "Twice the value is 4.", "claim_ids": [result.claims[0].claim_id]}]
    )
    assert "query REF-enumeration" in render(draft, answer, envelope.evidence, registry, plan)
    answer.claims[0].computation_ref = None
    answer.claims[0].citations = [
        CitationSelection(kind="computation", ref="artifact"),
        CitationSelection(kind="enumeration", ref="REF-enumeration"),
    ]
    assert validate_package(answer, {"root": envelope}, envelope.evidence, registry) == plan
    answer.claims[0].citations[-1] = CitationSelection(kind="enumeration", ref="artifact")
    with pytest.raises(ValueError, match="not a enumeration"):
        validate_package(answer, {"root": envelope}, envelope.evidence, registry)


def test_artifact_manifest_preserves_result_execution_and_coverage():
    from comtech.agents.budget import TokenCounter

    registry, _ = computation_fixture()
    manifest = registry.finalization_manifest(TokenCounter())["artifact"]
    assert manifest["result"] == "4"
    assert manifest["execution_verified"] and manifest["execution_ref"] == "exec"
    assert manifest["input_refs"] == ["EV-source"]
    assert not manifest["coverage"]["population_complete"]
    registry.payloads["payload"] = "long result " * 3000
    manifest = registry.finalization_manifest(TokenCounter())["artifact"]
    assert manifest["result"] is None and manifest["result_omitted"]
    assert manifest["execution_verified"]


def test_resolver_uses_a_contributor_with_complete_access_and_never_hides_corruption():
    from comtech.agents.citations import resolve_citations
    from comtech.agents.errors import ClaimValidationError

    registry, result = computation_fixture()
    registry.parents["partial-grant"] = None
    registry.grants["partial-grant"] = {"artifact"}
    resolved = registry.resolve("artifact", ["partial-grant", "root"], "computation")
    assert resolved["authorized_root"] == "root"
    answer = package(result.claims[0], [])
    registry.payloads["payload"] = "corrupt"
    with pytest.raises(ValueError, match="hash mismatch") as error:
        resolve_citations(answer, registry.evidence, registry)
    assert not isinstance(error.value, ClaimValidationError)  # No futile model repair.
