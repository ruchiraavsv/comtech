"""Application migration 5: durable scheduler transitions and dependency delivery."""

MIGRATION = """
ALTER TABLE research_tasks ADD COLUMN continuation jsonb NOT NULL DEFAULT '{}';
ALTER TABLE research_tasks ADD COLUMN admission_hash text;
ALTER TABLE research_tasks ADD COLUMN scope_key text NOT NULL DEFAULT 'supervisor';
ALTER TABLE research_tasks ADD COLUMN termination_reason text;
CREATE TABLE research_dependencies (
    objective_id uuid NOT NULL,
    parent_id uuid NOT NULL,
    child_id uuid NOT NULL,
    active boolean NOT NULL DEFAULT true,
    delivered boolean NOT NULL DEFAULT false,
    PRIMARY KEY(objective_id,parent_id,child_id),
    CHECK(parent_id<>child_id),
    FOREIGN KEY(objective_id,parent_id) REFERENCES research_tasks(objective_id,id),
    FOREIGN KEY(objective_id,child_id) REFERENCES research_tasks(objective_id,id)
);
CREATE TABLE research_task_transitions (
    objective_id uuid NOT NULL,
    task_id uuid NOT NULL,
    attempt_id uuid PRIMARY KEY,
    request_hash text NOT NULL,
    outcome jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY(objective_id,task_id,attempt_id)
        REFERENCES research_attempts(objective_id,task_id,id)
);
"""
