"""Domain contracts shared by graph nodes and source adapters."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Limits(Contract):
    max_sections_per_read: int = Field(default=3, ge=1, le=10)
    max_tokens_per_section: int = Field(default=1000, ge=64)
    max_tokens_per_read: int = Field(default=3000, ge=512)
    knowledge_worker_max_cycles: int = Field(default=5, ge=1, le=20)
    total_context_budget: int = Field(default=30000, ge=4000)
    finalization_reserve: int = Field(default=4000, ge=1000)
    decision_output_tokens: int = Field(default=1000, ge=128)
    max_review_cycles: int = Field(default=2, ge=1, le=4)
    max_tasks: int = Field(default=6, ge=1, le=20)
    parallel_workers: int = Field(default=1, ge=1, le=4)
    tool_timeout_seconds: float = Field(default=15, gt=0)
    worker_timeout_seconds: float = Field(default=90, gt=0)

    @model_validator(mode="after")
    def coherent(self):
        if self.exploration_budget <= self.max_tokens_per_read + self.decision_output_tokens:
            raise ValueError("Context budget leaves insufficient exploration capacity")
        if self.max_tokens_per_section > self.max_tokens_per_read:
            raise ValueError("Section limit exceeds read limit")
        return self

    @property
    def exploration_budget(self):
        return self.total_context_budget - self.finalization_reserve


class SourceRef(Contract):
    source_type: Literal[
        "document",
        "service_catalog",
        "employee_directory",
        "incident_record",
        "oncall_shift",
        "deployment",
    ]
    source_id: str
    version: str
    section_id: str | None = None
    record_id: str | None = None
    char_start: int | None = None
    char_end: int | None = None


class Observation(Contract):
    observation_id: str
    source_ref: SourceRef
    title: str
    content: str
    content_hash: str
    retrieved_at: str
    as_of: str | None = None
    updated_at: str | None = None
    effective_from: str | None = None
    effective_to: str | None = None
    is_partial: bool = False
    token_count: int | None = None
    remaining_spans: list[tuple[int, int]] = Field(default_factory=list)


class ToolFailure(Contract):
    tool_name: str
    code: str
    message: str


class ToolResult(Contract):
    observations: list[Observation] = Field(default_factory=list)
    details: str = ""
    error: ToolFailure | None = None


class ReadDocumentSectionsResult(ToolResult):
    document_id: str
    version: str
    token_count: int = 0
    omitted_sections: bool = False
    section_options: list[dict[str, str]] = Field(default_factory=list)
    section_options_truncated: bool = False


class KnowledgeTask(Contract):
    task_id: str
    objective: str
    complexity: Literal["simple", "complex"] = "simple"
    context: str = ""
    constraints: list[str] = Field(default_factory=list)
    expected_output: str = "Supported claims and unresolved information"
    source_hints: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)


class SupervisorPlan(Contract):
    resolved_request: str
    tasks: list[KnowledgeTask]


class Decision(Contract):
    action: Literal["tool", "finalize"]
    tool_name: str | None = None
    arguments_json: str = "{}"
    stop_due_to_tool_failure: bool = False


class UnresolvedItem(Contract):
    information_need: str
    reason: Literal["not_found", "insufficient_evidence", "ambiguous", "conflicting_evidence"]
    attempted_sources: list[str] = Field(default_factory=list)
    details: str


class ClarificationRequest(Contract):
    question: str


class Selection(Contract):
    observation_id: str
    role: Literal["support", "conflict", "context"] = "support"


class ClaimDraft(Contract):
    claim_id: str
    statement: str
    support: Literal["direct", "derived", "uncertain"]
    evidence: list[Selection]
    premise_claim_ids: list[str] = Field(default_factory=list)
    derivation: str | None = None


class SourceConflictDraft(Contract):
    description: str
    observation_ids: list[str]


class KnowledgeWorkerDraftResult(Contract):
    status: Literal["answered", "partial", "not_found", "needs_clarification"]
    claims: list[ClaimDraft]
    unresolved: list[UnresolvedItem]
    source_conflicts: list[SourceConflictDraft] = Field(default_factory=list)
    clarification: ClarificationRequest | None = None


class ClaimEvidenceLink(Contract):
    evidence_id: str
    role: Literal["support", "conflict", "context"]


class SupportedClaim(Contract):
    claim_id: str
    statement: str
    support: Literal["direct", "derived", "uncertain"]
    evidence: list[ClaimEvidenceLink]
    premise_claim_ids: list[str] = Field(default_factory=list)
    derivation: str | None = None
    computation_ref: str | None = None


class EvidenceRecord(Observation):
    evidence_id: str
    run_id: str
    task_id: str


class SourceConflict(Contract):
    description: str
    evidence_ids: list[str]


TerminationReason = Literal["completed", "cycle_limit", "context_budget", "tool_failure"]


class KnowledgeWorkerResult(Contract):
    task_id: str
    status: Literal["answered", "partial", "not_found", "needs_clarification"]
    termination_reason: TerminationReason
    claims: list[SupportedClaim]
    unresolved: list[UnresolvedItem]
    source_conflicts: list[SourceConflict]
    clarification: ClarificationRequest | None
    tool_failures: list[ToolFailure]


class CitationSelection(Contract):
    kind: Literal["source", "computation", "enumeration"]
    ref: str


class AnswerClaim(Contract):
    claim_id: str
    statement: str
    support: Literal["direct", "derived", "uncertain"]
    evidence_ids: list[str]
    premise_claim_ids: list[str] = Field(default_factory=list)
    derivation: str | None = None
    source_task_ids: list[str]
    computation_ref: str | None = None
    citations: list[CitationSelection] = Field(default_factory=list)


class SupervisorAnswerPackage(Contract):
    resolved_request: str
    claims: list[AnswerClaim]
    unresolved: list[UnresolvedItem]
    limitations: list[str]
    source_conflicts: list[SourceConflict]
    clarification: ClarificationRequest | None


class ReviewIssue(Contract):
    issue_type: str
    description: str
    affected_claim_ids: list[str]
    severity: Literal["warning", "blocking"]


class ReviewDecision(Contract):
    status: Literal["approved", "revise_supervisor"]
    issues: list[ReviewIssue]
    required_changes: list[str]
    followup_tasks: list[KnowledgeTask]


class RenderedParagraph(Contract):
    text: str = Field(
        description="User-facing prose only; no internal claim IDs or citation markup."
    )
    claim_ids: list[str] = Field(description="Approved claim IDs attributed to this paragraph.")


class FinalDraft(Contract):
    paragraphs: list[RenderedParagraph]
