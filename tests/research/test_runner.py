"""Actual isolated Linux runner plus real PostgreSQL and the synthetic R3 broker."""

import asyncio
import os
from dataclasses import replace
from uuid import uuid4

import pytest

from comtech.research.control import Control
from comtech.research.delivery import Delivery
from comtech.research.ledger import RunClosed
from comtech.research.python_execution import PythonExecutor
from comtech.research.queue import TaskQueue
from comtech.research.runner_client import RunnerClient
from comtech.research.runner_wire import DEFAULT_LIMITS

from .test_broker import bundle as bundle

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_RUNNER_TESTS") != "1", reason="Requires isolated R4 runner profile"
    ),
]


async def ready(client):
    async with asyncio.timeout(30):
        while True:
            try:
                description = await client.describe()
                if not description["busy"]:
                    return description
            except (OSError, EOFError):
                pass
            await asyncio.sleep(0.1)


@pytest.fixture
async def executor(bundle):
    client = RunnerClient(os.environ["RESEARCH_RUNNER_SOCKET"])
    description = await ready(client)
    assert description["environment"]["packages"] == {
        "numpy": "2.5.3",
        "pandas": "3.0.6",
        "pyarrow": "25.0.1",
        "python-dateutil": "2.9.0.post0",
        "six": "1.17.0",
    }
    yield PythonExecutor(bundle.broker, client, description["environment_digest"])
    await ready(client)


async def execute(executor, bundle, code, refs=None, key=None, limits=None):
    result = await executor.execute(
        bundle.ctx,
        code,
        "Synthetic acceptance calculation",
        refs or [],
        request_id=key or uuid4().hex,
        limits=limits,
    )
    if result["status"] != "success":
        async with bundle.caps.pool.connection() as conn:
            row = await (
                await conn.execute(
                    "SELECT record->'logs' AS logs FROM research_executions WHERE id=%s",
                    (result["execution_id"],),
                )
            ).fetchone()
            print("Synthetic runner diagnostics:", row["logs"])
    return result


async def test_failed_python_preserves_broker_feedback_and_source_receipts_but_not_artifacts(
    executor, bundle
):
    from comtech.research.access import Access
    from comtech.research.result_registry import ResultRegistry

    code = """
page = data.enumerate_documents({'fields':['document_id','version']})
data.write_artifact({'n':len(page['items'])}, 'json', list(data.receipt_refs),
                    method='Count versions')
data.enumerate_documents({'version_policy':'all_in_release'})
"""
    result = await execute(executor, bundle, code, key="bad-policy")
    assert result["status"] == "error" and result["error"] == "DataError"
    error = result["data_errors"][0]
    assert error["tool_name"] == "enumerate_documents" and error["code"] == "SCOPE_DENIED"
    assert "version_policy must be 'pinned'" in error["message"]
    assert len(result["receipt_refs"]) == 1
    registry = await ResultRegistry(bundle.broker).load(
        Access(bundle.ctx, bundle.scope, None, ""), result["receipt_refs"]
    )
    assert not registry.artifacts and registry.queries
    assert await execute(executor, bundle, code, key="bad-policy") == result
    corrected = await execute(
        executor, bundle, "result=data.enumerate_documents({'version_policy':'pinned'})"
    )
    assert corrected["status"] == "success" and not corrected["data_errors"]


async def test_oversized_python_result_keeps_successful_source_reads(executor, bundle):
    from comtech.research.access import Access
    from comtech.research.result_registry import ResultRegistry

    result = await execute(
        executor, bundle, "data.read_document_sections('DOC-0','commit'); result=list(range(2500))"
    )
    assert result["status"] == "resource_limit" and result["error"] == "result_token_limit"
    assert len(result["receipt_refs"]) == 1 and result["omitted_receipt_count"] == 0
    assert bundle.broker.counter.count(result) <= 3000
    registry = await ResultRegistry(bundle.broker).load(
        Access(bundle.ctx, bundle.scope, None, ""), result["receipt_refs"]
    )
    assert registry.evidence and not registry.artifacts


async def test_paginated_census_process_reaches_review_with_registered_support(executor, bundle):
    import json

    from comtech.research.access import Access
    from comtech.research.actions import ResearchDraft
    from comtech.research.result_registry import ResultRegistry

    # Unknown metadata and multiple pages must survive the reduction and its review context.
    bundle.store.documents["DOC-0"]["document_type"] = "policy"
    bundle.store.documents["DOC-1"]["document_type"] = "policy"
    bundle.store.documents["DOC-2"]["document_type"] = None
    code = """
from collections import Counter
rows, receipts, cursor = [], [], None
while True:
    page = data.enumerate_documents({
        'fields': ['document_id', 'version', 'document_type'], 'limit': 2, 'cursor': cursor})
    receipts.append(data.receipt_refs[-1])
    rows.extend(page['items'])
    cursor = page['next_cursor']
    if cursor is None:
        break
unique = {(r['document_id'], r['version']): r for r in rows}
counts = dict(Counter(r['document_type'] or 'unknown' for r in unique.values()))
value = {'counts': counts, 'rows_read': len(rows), 'unique_versions': len(unique),
         'grand_total': sum(counts.values()), 'pagination_exhausted': not page['truncated']}
process = {
    'summary': 'Enumerated all metadata pages, deduplicated by document_id and version, '
               'mapped absent types to unknown, grouped by type and summed the counts.',
    'population': 'Every document version in the pinned release; unit: document versions.',
    'checks': ['Read 3 rows and retained 3 unique versions.',
               'Category counts sum to 3; pagination exhausted.'],
    'limitations': ['Metadata census only; document content was not semantically inspected.']}
artifact = data.write_artifact(value, 'json', receipts, method='Document-version census',
    units='document versions', analysis_process=process)
result = {'artifact_ref': artifact['artifact_ref'], 'counts': counts}
"""
    output = await execute(executor, bundle, code)
    assert output["status"] == "success"
    assert output["value"]["counts"] == {"policy": 2, "unknown": 1}
    access = Access(bundle.ctx, bundle.scope, None, "")
    loader = ResultRegistry(bundle.broker)
    registry = await loader.load(access, output["receipt_refs"])
    artifact_ref = output["value"]["artifact_ref"]
    draft = ResearchDraft(
        status="answered",
        unresolved=[],
        claims=[
            {
                "claim_id": "census",
                "statement": "There are 2 policy versions and 1 unknown type.",
                "support": "derived",
                "evidence": [],
                "premise_claim_ids": [],
                "computation_ref": artifact_ref,
                "derivation": "Count unique versions by type over exhausted metadata pages.",
            }
        ],
    )
    envelope = loader.finalize(registry, str(bundle.ctx.lease.task_id), draft, "completed", [])
    registry.validate_export(envelope)
    review = registry.review_computations(bundle.broker.counter)[artifact_ref]
    assert review["manifest"]["analysis_process"]["checks"] == [
        "Read 3 rows and retained 3 unique versions.",
        "Category counts sum to 3; pagination exhausted.",
    ]
    assert review["execution"]["execution_ref"] == output["execution_id"]
    assert json.loads(review["result"])["grand_total"] == 3
    assert not review["result_omitted"]
    pages = sorted(review["input_coverage"].values(), key=lambda p: p["enumerated_through"])
    assert [(p["returned_count"], p["enumerated_through"]) for p in pages] == [(2, 2), (1, 3)]
    assert pages[0]["truncated"] and pages[0]["cursor"]
    assert not pages[1]["truncated"] and pages[1]["cursor"] is None
    assert len({p["population_hash"] for p in pages}) == 1
    assert all(p["semantic_inspection"] is False for p in pages)
    # Authored prose must not turn calculation coverage into a runtime completeness assertion.
    assert review["coverage"]["population_complete"] is False
    assert envelope.artifact_refs == [artifact_ref] and envelope.evidence == {}
    # The legacy path remains valid without the optional method summary.
    legacy = await execute(
        executor,
        bundle,
        "a = data.write_artifact({'n': 3}, 'json', input_refs, method='Copy known count'); "
        "result = {'artifact_ref': a['artifact_ref']}",
        refs=[artifact_ref],
    )
    assert legacy["status"] == "success"
    legacy_registry = await loader.load(access, legacy["receipt_refs"])
    assert legacy_registry.artifacts[legacy["value"]["artifact_ref"]].analysis_process is None


async def test_brokered_calculation_artifact_continuation_and_replay(executor, bundle):
    code = """
import numpy as np
found = data.knowledge_search('Alpha', service_ids=['svc-0'])
read = data.read_document_sections('DOC-0', 'commit')
rows = [{'length': len(o['content'])} for o in read['observations']]
artifact = data.write_artifact(rows, 'parquet',
    [o['observation_id'] for o in read['observations']], method='Selected span character lengths')
result = {'total': int(np.sum([r['length'] for r in rows])), 'artifact': artifact['artifact_ref']}
"""
    first = await execute(executor, bundle, code, key="calculation")
    assert first["status"] == "success", first
    assert first["value"]["total"] > 0 and first["receipt_refs"]
    again = await execute(executor, bundle, code, key="calculation")
    assert again == first
    with pytest.raises(ValueError, match="immutable"):
        await execute(executor, bundle, "result = 0", key="calculation")
    second = await execute(
        executor,
        bundle,
        """
import pandas as pd
page = data.read_artifact(input_refs[0])
result = {'total': int(pd.DataFrame(page['items'])['length'].sum())}
""",
        refs=[first["value"]["artifact"]],
    )
    assert second["status"] == "success", second
    assert second["value"]["total"] == first["value"]["total"]
    counters = await bundle.ctx.ledger.counters(bundle.ctx.lease.objective_id)
    assert counters["python_executions"]["used"] == 2
    assert counters["data_requests"]["used"] == 4
    async with bundle.caps.pool.connection() as conn:
        entry = await (
            await conn.execute(
                "SELECT record FROM research_executions WHERE id=%s", (first["execution_id"],)
            )
        ).fetchone()
        assert entry["record"]["code_hash"] and entry["record"]["environment_digest"]
        live = await (
            await conn.execute(
                "SELECT count(*) AS n FROM research_data_capabilities "
                "WHERE execution_id=%s AND NOT revoked",
                (first["execution_id"],),
            )
        ).fetchone()
        assert live["n"] == 0


async def test_generated_code_cannot_reach_network_secrets_control_or_processes(executor, bundle):
    result = await execute(
        executor,
        bundle,
        """
import os, socket, subprocess, pathlib, importlib.util, ctypes
denied = []
def refusal(label, operation):
    try:
        operation()
    except OSError as error:
        assert error.errno in (1,13,30), (label,error)
        denied.append(label)
destinations=['api.openai.com','pinecone.io','postgres',
              'northstar-mcp','169.254.169.254','127.0.0.1']
for destination in destinations:
    refusal(destination, lambda: socket.socket(socket.AF_INET, socket.SOCK_STREAM))
refusal('unix', lambda: socket.socket(socket.AF_UNIX))
refusal('ipv6', lambda: socket.socket(socket.AF_INET6))
refusal('fork', os.fork)
refusal('shell', lambda: subprocess.run(['/bin/sh','-c','true']))
refusal('escaped_session', lambda: subprocess.Popen(['/bin/sh'], start_new_session=True))
libc=ctypes.CDLL(None,use_errno=True)
assert libc.syscall(41,2,1,0)==-1 and ctypes.get_errno()==1  # Native x86_64 socket syscall
refusal('uid', lambda: os.setuid(10000))
refusal('signal', lambda: os.kill(1, 9))
refusal('control_files', lambda: list(pathlib.Path('/run/research-control').iterdir()))
refusal('supervisor_env', lambda: pathlib.Path('/proc/1/environ').read_bytes())
refusal('outside_workspace', lambda: pathlib.Path('/tmp/escape').write_text('forbidden'))
refusal('readonly_image', lambda: pathlib.Path('/opt/research/injected.py').write_text('forbidden'))
pathlib.Path('allowed.txt').write_text('allowed')
assert pathlib.Path('allowed.txt').read_text() == 'allowed'
for module in ['openai','pinecone','psycopg','pip']:
    assert importlib.util.find_spec(module) is None
assert not any('KEY' in k or 'TOKEN' in k or 'PASSWORD' in k for k in os.environ)
assert not pathlib.Path('/app').exists()
status=pathlib.Path('/proc/self/status').read_text()
caps = ('CapEff:', 'CapPrm:', 'CapAmb:', 'CapInh:')
assert all(int(line.split()[1],16)==0 for line in status.splitlines() if line.startswith(caps))
assert os.getuid()==10002
assert pathlib.Path('/sys/fs/cgroup/memory.max').read_text().strip()=='2147483648'
assert pathlib.Path('/sys/fs/cgroup/pids.max').read_text().strip()=='64'
result={'denied':denied}
""",
    )
    assert result["status"] == "success", result
    assert len(result["value"]["denied"]) == 17


@pytest.mark.parametrize(
    "code,limits,expected",
    [
        ("while True: pass", {**DEFAULT_LIMITS, "wall_seconds": 1}, "timeout"),
        (
            "while True: pass",
            {**DEFAULT_LIMITS, "cpu_seconds": 1, "wall_seconds": 10},
            "resource_limit",
        ),
        (
            "result = bytearray(256 * 1024**2)",
            {**DEFAULT_LIMITS, "memory_bytes": 32 * 1024**2},
            "resource_limit",
        ),
        ("print('x' * 20000); result = 1", DEFAULT_LIMITS, "resource_limit"),
        ("result = list(range(3000))", DEFAULT_LIMITS, "resource_limit"),
        (
            "with open('large', 'wb') as f:\n"
            " for _ in range(40): f.write(b'x' * 1024**2)\nresult=1",
            DEFAULT_LIMITS,
            "resource_limit",
        ),
        (
            "from pathlib import Path\n"
            "for n in range(12): Path(str(n)).write_bytes(b'x' * 8 * 1024**2)\nresult=1",
            DEFAULT_LIMITS,
            "resource_limit",
        ),
    ],
)
async def test_limits_fail_bounded_and_runner_recovers(executor, bundle, code, limits, expected):
    failed = await execute(executor, bundle, code, limits=limits)
    assert failed["status"] == expected, failed
    success = await execute(executor, bundle, "result = 6 * 7")
    assert success["status"] == "success" and success["value"] == 42, success


async def test_forged_data_and_cleanup_of_hostile_permissions(executor, bundle):
    result = await execute(
        executor,
        bundle,
        """
import os, pathlib
errors=[]
for operation,args in [('grant',{}),('read_artifact',{'artifact_ref':'forged'}),
                       ('enumerate_documents',{'fields':['source_locator']})]:
    try: data._call(operation,args)
    except Exception as exc: errors.append(exc.code)
pathlib.Path('nested').mkdir()
pathlib.Path('nested/value').write_text('temporary')
os.chmod('nested',0)
result = errors
""",
    )
    assert result["status"] == "success", result
    assert result["value"] == ["CAPABILITY_UNAVAILABLE", "INVALID_REFERENCE", "INVALID_ARGUMENT"]
    following = await execute(
        executor, bundle, "import pathlib; result = list(pathlib.Path('.').iterdir())"
    )
    assert following["status"] == "success" and following["value"] == [], following


async def test_explicit_cancel_revokes_capability_and_stops_runner(executor, bundle):
    running = asyncio.create_task(
        execute(executor, bundle, "import time; time.sleep(60); result=1")
    )
    async with asyncio.timeout(10):
        while not (await executor.runner.describe())["busy"]:  # noqa: ASYNC110 - remote status
            await asyncio.sleep(0.05)
    await Control(bundle.caps.pool, Delivery(bundle.caps.pool)).cancel(bundle.run["id"])
    with pytest.raises(RunClosed):
        await running
    async with asyncio.timeout(5):
        await bundle.ctx.resources.drain()
        await ready(executor.runner)
    async with bundle.caps.pool.connection() as conn:
        active = await (
            await conn.execute(
                "SELECT count(*) AS n FROM research_data_capabilities "
                "WHERE objective_id=%s AND NOT revoked",
                (bundle.ctx.lease.objective_id,),
            )
        ).fetchone()
        assert active["n"] == 0


async def test_library_threads_inherit_boundary_and_pid_limit(executor, bundle):
    result = await execute(
        executor,
        bundle,
        """
import threading, socket, pyarrow as pa
table=pa.table({'group':['a','a','b'], 'value':[1,2,3]})
assert table.group_by('group').aggregate([('value','sum')]).num_rows==2
stop=threading.Event()
threads=[]
denied=[]
def worker():
    try: socket.socket()
    except PermissionError: denied.append(True)
    stop.wait()
try:
    for _ in range(50):
        t=threading.Thread(target=worker)
        t.start()
        threads.append(t)
except RuntimeError:
    pass
finally:
    stop.set()
    for t in threads: t.join()
result={'started':len(threads),'denied':len(denied)}
""",
    )
    assert result["status"] == "success", result
    assert 1 <= result["value"]["started"] < 16
    assert result["value"]["denied"] == result["value"]["started"]


async def test_client_disconnect_terminates_job_and_releases_slot(executor, bundle):
    task = asyncio.create_task(execute(executor, bundle, "import time; time.sleep(60); result=1"))
    async with asyncio.timeout(10):
        while not (await executor.runner.describe())["busy"]:  # noqa: ASYNC110
            await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    async with asyncio.timeout(5):
        await bundle.ctx.resources.drain()
        await ready(executor.runner)
    result = await execute(executor, bundle, "result=42")
    assert result["status"] == "success", result


async def test_committed_execution_replays_after_recovery_and_retention(executor, bundle):
    code = "print('synthetic audit'); result=42"
    first = await execute(executor, bundle, code, key="durable")
    assert first["status"] == "success", first
    counts = await bundle.ctx.ledger.counters(bundle.ctx.lease.objective_id)
    await Control(bundle.caps.pool, Delivery(bundle.caps.pool)).recover(
        bundle.scope.pinned_versions
    )
    claim = await TaskQueue(bundle.caps.pool).claim(uuid4(), ["supervisor"])
    bundle.ctx = replace(bundle.ctx, lease=claim.lease)
    replay = await execute(executor, bundle, code, key="durable")
    assert replay == first
    assert await bundle.ctx.ledger.counters(bundle.ctx.lease.objective_id) == counts
    async with bundle.caps.pool.connection() as conn:
        await conn.execute(
            "UPDATE research_executions SET created_at=now()-interval '8 days', "
            "record=jsonb_set(record,'{logs_expires_at}','0') WHERE id=%s",
            (first["execution_id"],),
        )
    await executor.prune()
    async with bundle.caps.pool.connection() as conn:
        row = await (
            await conn.execute(
                "SELECT record FROM research_executions WHERE id=%s", (first["execution_id"],)
            )
        ).fetchone()
        assert row["record"]["code"] == code and "logs" not in row["record"]
    await Control(bundle.caps.pool, Delivery(bundle.caps.pool)).cancel(bundle.run["id"])
    await executor.prune()
    async with bundle.caps.pool.connection() as conn:
        row = await (
            await conn.execute(
                "SELECT record FROM research_executions WHERE id=%s", (first["execution_id"],)
            )
        ).fetchone()
        assert "code" not in row["record"] and row["record"]["code_hash"]
        assert row["record"]["output"] == first


async def test_unavailable_runner_and_broker_do_not_fall_back(executor, bundle, monkeypatch):
    missing = PythonExecutor(
        bundle.broker, RunnerClient("/no-runner.sock"), executor.environment_digest
    )
    result = await execute(missing, bundle, "result=42")
    assert result["status"] == "error" and result["error"] == "runner_unavailable"

    from comtech.research.broker_contracts import BrokerError

    async def unavailable(*args, **kwargs):
        raise BrokerError("UNAVAILABLE", "Synthetic source outage")

    monkeypatch.setattr(bundle.broker, "call", unavailable)
    result = await execute(executor, bundle, "result=data.knowledge_search('Alpha')")
    assert result["status"] == "error", result
    assert not bundle.requests and not bundle.embeddings


@pytest.mark.skipif(os.getenv("RUN_RUNNER_RESTART_TEST") != "1", reason="Host-orchestrated restart")
async def test_container_restart_during_execution(executor, bundle):
    code = "import time; time.sleep(60); result=1"
    task = asyncio.create_task(execute(executor, bundle, code, key="restart"))
    async with asyncio.timeout(10):
        while not (await executor.runner.describe())["busy"]:  # noqa: ASYNC110
            await asyncio.sleep(0.05)
    print("RESTART_READY", flush=True)
    result = await task
    assert result["status"] == "error", result
    await ready(executor.runner)
    before = await bundle.ctx.ledger.counters(bundle.ctx.lease.objective_id)
    assert await execute(executor, bundle, code, key="restart") == result
    assert await bundle.ctx.ledger.counters(bundle.ctx.lease.objective_id) == before
    fresh = await execute(
        executor,
        bundle,
        "import pathlib; result=len(list(pathlib.Path('/tmp').glob('research-*')))",
    )
    assert fresh["status"] == "success" and fresh["value"] == 1, fresh
