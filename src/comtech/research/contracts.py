"""Versioned research boundaries, separate from the legacy worker wire contract.

Identity, scope and lineage records are populated by trusted orchestration. Defining
these types does not grant a model permission to create registered records.
"""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, model_validator

from comtech.agents.contracts import (
    Contract,
    EvidenceRecord,
    KnowledgeTask,
    KnowledgeWorkerResult,
    SupervisorAnswerPackage,
    SupportedClaim,
)

AnalysisMode = Literal["semantic", "deterministic", "mixed"]
TaskState = Literal[
    "pending", "running", "waiting_children", "finalizing", "completed", "failed", "cancelled"
]
RunState = Literal[
    "queued",
    "running",
    "waiting",
    "cancel_requested",
    "completed",
    "failed",
    "cancelled",
    "interrupted",
]


class Versioned(Contract):
    schema_version: Literal[1] = 1


class SourceScope(Versioned):
    scope_ref: str
    sources: list[str]
    datasets: dict[str, list[str]]
    fields: dict[str, list[str]]
    capabilities: list[str]
    pinned_versions: dict[str, str]
    document_ids: list[str] | None = None
    record_ids: list[str] | None = None
    time_start: datetime | None = None
    time_end: datetime | None = None
    document_version_policy: Literal["pinned", "latest_in_release", "all_in_release"] = "pinned"


class ResearchObjective(Versioned):
    objective_id: str
    run_id: str
    thread_id: str
    question: str
    output_requirements: list[str]
    scope_ref: str
    pinned_versions: dict[str, str]
    budget_profile: str
    created_at: datetime
    deadline: datetime
    exploration_deadline: datetime

    @model_validator(mode="after")
    def deadlines(self):
        if not self.created_at < self.exploration_deadline < self.deadline:
            raise ValueError("Exploration must leave time for finalization")
        return self


class ResearchTask(Versioned):
    task_id: str
    objective_id: str
    parent_task_id: str | None
    depth: int = Field(ge=0)
    analysis_key: str
    objective: str
    analysis_mode: AnalysisMode
    scope_ref: str
    expected_output: str
    input_refs: list[str] = Field(default_factory=list)
    unresolved_gaps: list[str] = Field(default_factory=list)
    prompt_version: str = "research-v1"


class ResearchRequest(Versioned):
    """Model proposal; canonical objective/run/scope binding happens outside the model."""

    task_id: str
    objective: str
    analysis_mode: AnalysisMode
    expected_output: str
    document_ids: list[str] | None = Field(
        default=None,
        max_length=1000,
        description="Optional document ID allowlist. Null inherits document scope.",
    )
    input_refs: list[str] = Field(
        default_factory=list,
        max_length=100,
        description=(
            "Only durable references from available_research_input_refs. Use [] for fresh "
            "research. Document IDs, worker claim IDs and ordinary worker evidence IDs are "
            "not registered Research inputs; select documents with document_ids instead."
        ),
    )


class KnowledgeDelegation(Versioned):
    specialist: Literal["knowledge_worker"] = "knowledge_worker"
    task: KnowledgeTask


class ResearchDelegation(Versioned):
    specialist: Literal["research"] = "research"
    task: ResearchRequest


Delegation = Annotated[KnowledgeDelegation | ResearchDelegation, Field(discriminator="specialist")]


class DelegateAction(Versioned):
    action: Literal["delegate"] = "delegate"
    resolved_request: str
    calls: list[Delegation] = Field(min_length=1)


class SubmitAction(Versioned):
    action: Literal["submit"] = "submit"
    answer: SupervisorAnswerPackage


class SupervisorTurn(Versioned):
    decision: Annotated[DelegateAction | SubmitAction, Field(discriminator="action")]


class Coverage(Versioned):
    coverage_ref: str
    requested_scope_ref: str
    inspected_refs: list[str]
    relevant_omissions: list[str] = Field(default_factory=list)
    population_definition: str | None = None
    population_hash: str | None = None
    pinned_versions: dict[str, str] = Field(default_factory=dict)
    method: Literal["targeted", "sample", "enumeration", "aggregate"] = "targeted"
    inspected_count: int | None = Field(default=None, ge=0)
    total_count: int | None = Field(default=None, ge=0)
    truncated: bool = False
    cursor: str | None = None
    returned_count: int | None = Field(default=None, ge=0)
    enumerated_through: int | None = Field(default=None, ge=0)
    population_complete: bool = False
    semantic_inspection: bool | None = None

    @model_validator(mode="after")
    def counts(self):
        if (
            self.inspected_count is not None
            and self.total_count is not None
            and self.inspected_count > self.total_count
        ):
            raise ValueError("Inspected count exceeds known population")
        return self


class ExtendedWorkerResult(KnowledgeWorkerResult):
    schema_version: Literal[2] = 2
    termination_reason: Literal[
        "completed",
        "cycle_limit",
        "context_budget",
        "tool_failure",
        "objective_budget",
        "deadline",
        "no_progress",
        "depth_limit",
    ]


class QueryRecord(Versioned):
    reference_type: Literal["collection_query"] = "collection_query"
    query_ref: str
    run_id: str
    objective_id: str
    task_id: str
    source_id: str
    snapshot: str
    normalized_query: str
    selected_fields: list[str]
    coverage_ref: str
    result_ref: str
    result_hash: str


class ExecutionRecord(Versioned):
    execution_ref: str
    run_id: str
    objective_id: str
    task_id: str
    code_hash: str
    environment_digest: str
    input_refs: list[str]
    output_refs: list[str]
    started_at: datetime
    finished_at: datetime
    limits: dict[str, float]


class AnalysisProcess(Contract):
    """Author-reported method summary, checked against registered inputs and results."""

    summary: str = Field(
        min_length=1,
        max_length=2000,
        description="Concise reproducible procedure actually executed, not private reasoning.",
    )
    population: str = Field(
        min_length=1,
        max_length=1000,
        description="Input population, filters, time/version scope, and count unit.",
    )
    checks: list[Annotated[str, Field(min_length=1, max_length=500)]] = Field(
        default_factory=list,
        max_length=10,
        description="Checks actually performed, with outcomes present in the artifact result.",
    )
    limitations: list[Annotated[str, Field(min_length=1, max_length=500)]] = Field(
        default_factory=list,
        max_length=10,
        description="Missing coverage, extraction uncertainty, and other limits on interpretation.",
    )


class AnalysisArtifact(Versioned):
    reference_type: Literal["analysis_artifact"] = "analysis_artifact"
    artifact_ref: str
    run_id: str
    objective_id: str
    task_id: str
    execution_ref: str
    method: str
    input_refs: list[str]
    result_ref: str
    result_hash: str
    units: str | None
    assumptions: list[str]
    coverage_ref: str
    extraction_version: str | None = None
    analysis_provenance: dict[str, str] = Field(default_factory=dict)
    analysis_process: AnalysisProcess | None = None


class ClaimInheritance(Versioned):
    root_task_id: str
    originating_task_id: str
    claim_id: str


class RegisteredClaim(Versioned):
    run_id: str
    objective_id: str
    task_id: str
    claim: SupportedClaim


class SpecialistResult(Versioned):
    specialist: Literal["knowledge_worker", "research"]
    result: ExtendedWorkerResult
    evidence: dict[str, EvidenceRecord]
    coverage_refs: list[str] = Field(default_factory=list)
    execution_refs: list[str] = Field(default_factory=list)
    artifact_refs: list[str] = Field(default_factory=list)
    inheritance: list[ClaimInheritance] = Field(default_factory=list)


def parse_worker_result(value: dict) -> KnowledgeWorkerResult:
    """No version means the original contract, never an implicit migration."""
    if "schema_version" not in value:
        return KnowledgeWorkerResult.model_validate(value)
    return ExtendedWorkerResult.model_validate(value)
