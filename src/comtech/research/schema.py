"""Application migration 3; LangGraph continues to own its checkpoint schema."""

MIGRATION = """
ALTER TABLE app_runs DROP CONSTRAINT app_runs_status_check;
ALTER TABLE app_runs ADD CONSTRAINT app_runs_status_check CHECK (status IN
    ('queued','running','waiting','cancel_requested','completed','failed','cancelled','interrupted'));
ALTER TABLE app_runs ADD COLUMN execution_mode text NOT NULL DEFAULT 'stream'
    CHECK (execution_mode IN ('stream','background'));
ALTER TABLE app_runs ADD COLUMN graph_run_id uuid;
ALTER TABLE app_runs ADD COLUMN graph_version integer;
ALTER TABLE app_runs ADD COLUMN idempotency_key text;
ALTER TABLE app_runs ADD COLUMN request_hash text;
ALTER TABLE app_runs ADD COLUMN input jsonb;
ALTER TABLE app_runs ADD COLUMN terminal_reason text;
ALTER TABLE app_runs ADD COLUMN result jsonb;
ALTER TABLE app_runs ADD COLUMN event_sequence bigint NOT NULL DEFAULT 0 CHECK (event_sequence>=0);
UPDATE app_runs r SET event_sequence=COALESCE(
    (SELECT MAX(sequence) FROM app_run_events e WHERE e.run_id=r.id),0);
ALTER TABLE app_runs ADD CONSTRAINT app_runs_background_identity CHECK (
    execution_mode <> 'background' OR (
        graph_run_id IS NOT NULL AND graph_run_id=id AND graph_version IS NOT NULL
        AND idempotency_key IS NOT NULL AND length(idempotency_key) BETWEEN 1 AND 200
        AND request_hash IS NOT NULL AND input IS NOT NULL));
ALTER TABLE app_runs ADD UNIQUE(id,thread_id,execution_mode);
CREATE UNIQUE INDEX app_runs_submission ON app_runs(thread_id,idempotency_key)
    WHERE idempotency_key IS NOT NULL;
CREATE UNIQUE INDEX app_runs_one_active_thread ON app_runs(thread_id)
    WHERE status IN ('queued','running','waiting','cancel_requested')
       OR (execution_mode='background' AND status='interrupted');

CREATE TABLE research_objectives (
    id uuid PRIMARY KEY,
    schema_version integer NOT NULL DEFAULT 1 CHECK (schema_version=1),
    run_id uuid NOT NULL UNIQUE,
    thread_id uuid NOT NULL,
    execution_mode text NOT NULL DEFAULT 'background' CHECK (execution_mode='background'),
    scope jsonb NOT NULL,
    pinned_versions jsonb NOT NULL,
    budget_profile jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    exploration_deadline timestamptz NOT NULL,
    deadline timestamptz NOT NULL,
    cancel_requested_at timestamptz,
    FOREIGN KEY(run_id,thread_id,execution_mode) REFERENCES app_runs(id,thread_id,execution_mode),
    CHECK (created_at < exploration_deadline AND exploration_deadline < deadline)
);
CREATE TABLE research_tasks (
    id uuid PRIMARY KEY,
    schema_version integer NOT NULL DEFAULT 1 CHECK (schema_version=1),
    objective_id uuid NOT NULL REFERENCES research_objectives(id),
    parent_id uuid,
    logical_key text NOT NULL,
    kind text NOT NULL CHECK (kind IN ('supervisor','knowledge_worker','research')),
    state text NOT NULL DEFAULT 'pending' CHECK (state IN
        ('pending','running','waiting_children','finalizing','completed','failed','cancelled')),
    input jsonb NOT NULL,
    result jsonb,
    checkpoint_id text,
    fence bigint NOT NULL DEFAULT 0 CHECK (fence>=0),
    lease_owner uuid,
    lease_expires_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(objective_id,id),
    UNIQUE(objective_id,logical_key),
    FOREIGN KEY(objective_id,parent_id) REFERENCES research_tasks(objective_id,id),
    CHECK (parent_id IS NULL OR parent_id<>id)
);
CREATE INDEX research_tasks_ready ON research_tasks(state,created_at);
CREATE TABLE research_attempts (
    id uuid PRIMARY KEY,
    objective_id uuid NOT NULL,
    task_id uuid NOT NULL,
    fence bigint NOT NULL CHECK(fence>0),
    owner uuid NOT NULL,
    state text NOT NULL CHECK(state IN ('running','settled','uncertain','failed','cancelled')),
    started_at timestamptz NOT NULL DEFAULT now(),
    settled_at timestamptz,
    UNIQUE(objective_id,task_id,id),
    UNIQUE(task_id,fence),
    FOREIGN KEY(objective_id,task_id) REFERENCES research_tasks(objective_id,id)
);
CREATE TABLE research_budget_counters (
    objective_id uuid NOT NULL REFERENCES research_objectives(id),
    metric text NOT NULL,
    ceiling bigint NOT NULL CHECK(ceiling>=0),
    used bigint NOT NULL DEFAULT 0 CHECK(used>=0),
    reserved bigint NOT NULL DEFAULT 0 CHECK(reserved>=0),
    protected bigint NOT NULL DEFAULT 0 CHECK(protected>=0),
    PRIMARY KEY(objective_id,metric),
    CHECK(used+reserved+protected<=ceiling)
);
CREATE TABLE research_reservations (
    id uuid PRIMARY KEY,
    objective_id uuid NOT NULL,
    task_id uuid NOT NULL,
    attempt_id uuid NOT NULL,
    operation_key text NOT NULL,
    phase text NOT NULL CHECK(phase IN ('exploration','finalization')),
    state text NOT NULL CHECK(state IN ('reserved','inflight','settled','uncertain','released')),
    created_at timestamptz NOT NULL DEFAULT now(),
    settled_at timestamptz,
    UNIQUE(objective_id,id),
    UNIQUE(attempt_id,operation_key),
    FOREIGN KEY(objective_id,task_id,attempt_id)
        REFERENCES research_attempts(objective_id,task_id,id)
);
CREATE TABLE research_reservation_amounts (
    objective_id uuid NOT NULL,
    reservation_id uuid NOT NULL,
    metric text NOT NULL,
    amount bigint NOT NULL CHECK(amount>=0),
    actual bigint CHECK(actual>=0),
    PRIMARY KEY(reservation_id,metric),
    FOREIGN KEY(objective_id,reservation_id) REFERENCES research_reservations(objective_id,id),
    FOREIGN KEY(objective_id,metric) REFERENCES research_budget_counters(objective_id,metric)
);
CREATE TABLE research_executions (
    id uuid PRIMARY KEY,
    objective_id uuid NOT NULL,
    task_id uuid NOT NULL,
    attempt_id uuid NOT NULL,
    operation_key text NOT NULL,
    request_hash text NOT NULL,
    state text NOT NULL CHECK(state IN
        ('pending','running','success','failed','uncertain','cancelled')),
    record jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(objective_id,task_id,id),
    UNIQUE(task_id,operation_key),
    FOREIGN KEY(objective_id,task_id,attempt_id)
        REFERENCES research_attempts(objective_id,task_id,id)
);
CREATE TABLE research_artifacts (
    id uuid PRIMARY KEY,
    objective_id uuid NOT NULL,
    task_id uuid NOT NULL,
    execution_id uuid NOT NULL,
    state text NOT NULL CHECK(state IN ('writing','committed','expired')),
    content_hash text,
    record jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz,
    FOREIGN KEY(objective_id,task_id,execution_id)
        REFERENCES research_executions(objective_id,task_id,id)
);
"""
