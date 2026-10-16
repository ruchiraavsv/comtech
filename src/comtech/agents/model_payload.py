"""Model-only projections; durable evidence and validation retain full records."""

AUDIT_FIELDS = {"content_hash", "run_id", "task_id", "retrieved_at", "token_count"}


def source_record(record):
    return {
        key: {k: v for k, v in value.items() if v is not None} if key == "source_ref" else value
        for key, value in record.items()
        if key not in AUDIT_FIELDS and value is not None
    }


def model_payload(role, payload):
    data = dict(payload)
    if isinstance(data.get("evidence"), dict):
        data["evidence"] = {key: source_record(value) for key, value in data["evidence"].items()}
    if isinstance(data.get("observations"), list):
        data["observations"] = [source_record(value) for value in data["observations"]]
    if role == "review" and "citation_plan" in data:
        # Ownership is resolved already; full descriptions and transitive IDs remain
        # in the durable plan. Computation manifests supply methods and coverage once.
        data["citation_plan"] = {
            claim: [
                {
                    k: v
                    for k, v in citation.items()
                    if k in ("kind", "ref", "origin_task_id", "authorized_root")
                }
                for citation in citations
            ]
            for claim, citations in data["citation_plan"].items()
        }
    if role == "research":
        # Native API tools already carry these exact request schemas.
        advertised = data.pop("tools", {})
        if "sdk_schemas" in data:
            data["sdk_schemas"] = {
                key: value for key, value in data["sdk_schemas"].items() if key not in advertised
            }
    if role in ("research", "research_finalize") and "task" in data:
        task = dict(data["task"])
        for key, original in (
            ("gap", "description"),
            ("expected_information_gain", "expected_output"),
        ):
            if key in task and task[key] == task.get(original):
                task.pop(key)
        data["task"] = task
    return data
