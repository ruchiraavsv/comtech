"""Migration 7: immutable task scopes, short-lived capabilities and durable data refs."""

MIGRATION = """
CREATE TABLE research_data_scopes (
    task_id uuid PRIMARY KEY,
    objective_id uuid NOT NULL,
    scope jsonb NOT NULL,
    UNIQUE(objective_id,task_id),
    FOREIGN KEY(objective_id,task_id) REFERENCES research_tasks(objective_id,id)
);
CREATE TABLE research_data_capabilities (
    token_hash text PRIMARY KEY,
    objective_id uuid NOT NULL,
    task_id uuid NOT NULL,
    attempt_id uuid NOT NULL,
    execution_id uuid,
    expires_at timestamptz NOT NULL,
    revoked boolean NOT NULL DEFAULT false,
    FOREIGN KEY(objective_id,task_id) REFERENCES research_data_scopes(objective_id,task_id),
    FOREIGN KEY(objective_id,task_id,attempt_id)
        REFERENCES research_attempts(objective_id,task_id,id),
    FOREIGN KEY(objective_id,task_id,execution_id)
        REFERENCES research_executions(objective_id,task_id,id)
);
CREATE TABLE research_data_records (
    ref text PRIMARY KEY,
    objective_id uuid NOT NULL,
    task_id uuid NOT NULL,
    execution_id uuid,
    kind text NOT NULL CHECK(kind IN ('document','observation','page','artifact')),
    payload jsonb NOT NULL,
    content_hash text NOT NULL,
    source_scope jsonb NOT NULL,
    coverage jsonb NOT NULL,
    input_refs jsonb NOT NULL DEFAULT '[]',
    expires_at timestamptz NOT NULL DEFAULT now()+interval '7 days',
    expired boolean NOT NULL DEFAULT false,
    file_deleted boolean NOT NULL DEFAULT false,
    retained boolean NOT NULL DEFAULT false,
    FOREIGN KEY(objective_id,task_id) REFERENCES research_data_scopes(objective_id,task_id),
    FOREIGN KEY(objective_id,task_id,execution_id)
        REFERENCES research_executions(objective_id,task_id,id)
);
CREATE TABLE research_data_grants (
    ref text NOT NULL REFERENCES research_data_records(ref),
    task_id uuid NOT NULL REFERENCES research_data_scopes(task_id),
    PRIMARY KEY(ref,task_id)
);
CREATE TABLE research_data_cursors (
    token text PRIMARY KEY,
    objective_id uuid NOT NULL,
    task_id uuid NOT NULL,
    request_hash text NOT NULL,
    offset_value bigint NOT NULL CHECK(offset_value>=0),
    FOREIGN KEY(objective_id,task_id) REFERENCES research_data_scopes(objective_id,task_id)
);
CREATE INDEX research_data_retention ON research_data_records(expires_at)
    WHERE NOT expired;
CREATE TABLE research_data_requests (
    task_id uuid NOT NULL REFERENCES research_data_scopes(task_id),
    binding text NOT NULL,
    request_id text NOT NULL,
    request_hash text NOT NULL,
    PRIMARY KEY(task_id,binding,request_id)
);
"""
