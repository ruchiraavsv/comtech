import pytest
from pydantic import ValidationError

from comtech.agents.contracts import KnowledgeTask, KnowledgeWorkerResult
from comtech.research.contracts import Coverage, ExtendedWorkerResult, parse_worker_result


def result(**updates):
    return dict(
        task_id="root",
        status="answered",
        termination_reason="completed",
        claims=[],
        unresolved=[],
        source_conflicts=[],
        clarification=None,
        tool_failures=[],
        **updates,
    )


def test_legacy_parsing_is_explicit_and_complexity_keeps_its_meaning():
    legacy = result()
    assert type(parse_worker_result(legacy)) is KnowledgeWorkerResult
    assert type(parse_worker_result({**legacy, "schema_version": 2})) is ExtendedWorkerResult
    for version in (1, 3):
        with pytest.raises(ValidationError):
            parse_worker_result({**legacy, "schema_version": version})
    with pytest.raises(ValidationError):
        KnowledgeTask(task_id="k", objective="fact", complexity="research")


def test_early_answer_does_not_require_population_counts_or_completed_stop():
    coverage = Coverage(coverage_ref="cov", requested_scope_ref="scope", inspected_refs=["one"])
    assert coverage.total_count is None
    answered = ExtendedWorkerResult.model_validate(
        {**result(), "termination_reason": "context_budget"}
    )
    assert answered.status == "answered"
    with pytest.raises(ValidationError):
        ExtendedWorkerResult.model_validate({**result(), "status": "waiting_children"})
    with pytest.raises(ValidationError):
        Coverage(coverage_ref="cov", requested_scope_ref="scope", inspected_refs=[], extra=True)
