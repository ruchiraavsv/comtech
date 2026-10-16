"""Versioned cumulative budget profile; local model context limits remain separate."""

from pydantic import Field, StrictInt, model_validator

from .contracts import Versioned

DEFAULT_LIMITS = {
    "model_tokens": 250_000,
    "model_requests": 80,
    "embedding_tokens": 20_000,
    "embedding_requests": 30,
    "data_requests": 120,
    "source_requests": 240,
    "rows": 100_000,
    "bytes": 64 * 1024 * 1024,
    "retries": 10,
    "control_steps": 160,
    "supervisor_steps": 12,
    "specialist_calls": 6,
    "research_tasks": 24,
    "python_executions": 40,
    "documents_discovered": 500,
    "documents_opened": 200,
}


class BudgetProfile(Versioned):
    limits: dict[str, StrictInt] = Field(default_factory=lambda: dict(DEFAULT_LIMITS))
    final_reserve: dict[str, StrictInt] = Field(
        default_factory=lambda: {
            "model_tokens": 24_000,
            "model_requests": 10,
            "control_steps": 10,
            "retries": 5,
            "supervisor_steps": 4,
        }
    )

    @model_validator(mode="after")
    def coherent(self):
        if set(self.limits) != set(DEFAULT_LIMITS):
            raise ValueError("Budget profile must declare all supported counters")
        for metric, value in [*self.limits.items(), *self.final_reserve.items()]:
            if metric not in DEFAULT_LIMITS or type(value) is not int or value < 0:
                raise ValueError("Invalid budget metric or amount")
        if any(v > self.limits[k] for k, v in self.final_reserve.items()):
            raise ValueError("Finalization reserve exceeds objective ceiling")
        return self


def worker_reserve(limits):
    # Two structural finalization attempts, each with at most two provider attempts.
    return {
        "model_tokens": 4 * limits.total_context_budget,
        "model_requests": 4,
        "control_steps": 4,
        "retries": 2,
    }


MIGRATION = """
ALTER TABLE research_objectives ADD COLUMN accounting_error text;
CREATE TABLE research_budget_holds (
    objective_id uuid NOT NULL REFERENCES research_objectives(id),
    scope_key text NOT NULL,
    allocation jsonb NOT NULL,
    closed boolean NOT NULL DEFAULT false,
    PRIMARY KEY(objective_id,scope_key)
);
CREATE TABLE research_hold_amounts (
    objective_id uuid NOT NULL,
    scope_key text NOT NULL,
    metric text NOT NULL,
    remaining bigint NOT NULL CHECK(remaining>=0),
    PRIMARY KEY(objective_id,scope_key,metric),
    FOREIGN KEY(objective_id,scope_key) REFERENCES research_budget_holds(objective_id,scope_key),
    FOREIGN KEY(objective_id,metric) REFERENCES research_budget_counters(objective_id,metric)
);
ALTER TABLE research_reservations ADD COLUMN scope_key text NOT NULL DEFAULT 'supervisor';
ALTER TABLE research_reservations ADD COLUMN request_hash text;
ALTER TABLE research_reservations ADD COLUMN receipt jsonb;
ALTER TABLE research_reservations ADD COLUMN document_receipt jsonb;
ALTER TABLE research_reservation_amounts ADD COLUMN protected_draw bigint NOT NULL DEFAULT 0
    CHECK(protected_draw>=0 AND protected_draw<=amount);
CREATE TABLE research_document_usage (
    objective_id uuid NOT NULL REFERENCES research_objectives(id),
    metric text NOT NULL CHECK(metric IN ('documents_discovered','documents_opened')),
    source_key text NOT NULL,
    PRIMARY KEY(objective_id,metric,source_key)
);
"""
