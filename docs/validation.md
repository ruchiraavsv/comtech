# Infrastructure validation

Verified locally on 2026-09-27 with Podman 5.8.2, the existing WSL machine,
Compose provider 5.1.4, and locked Python 3.12 dependencies.

## Passed

- Windows preflight and `.cmd`/PowerShell argument-forwarding wrapper.
- API/UI container builds and development startup; migration service completes;
  Postgres, API readiness, and Streamlit health checks succeed.
- Six automated tests on Windows and six in Linux containers with isolated
  PostgreSQL 16.10. These cover incremental streaming before completion, same-thread
  conflict handling, independent conversations, session memory, durable history,
  cursor replay without execution, deliberate failure, timeout, disconnect,
  checkpoint resume, and rejection of accidental hosted targets in local tests.
- `scripts/verify_restart.py`: killed the API mid-node, restarted Postgres and API,
  verified interrupted status and durable progress, resumed the checkpoint, and
  confirmed the original recorded events were unchanged.
- Streamlit AppTest submitted a message to the live API and rendered the response
  without exceptions. This is a programmatic UI test, not a browser visual review.
- Pinecone Local container smoke test: known-vector upsert/query, metadata filter,
  namespace isolation, and fixture cleanup. No OpenAI calls or provider keys used.
- Remote Compose configuration validation: normal services are Postgres, migrate,
  API, UI, and HTTPS proxy; Pinecone Local is excluded unless explicitly opted in.
- Both Railway-style builds (`APP_TARGET=api` and `APP_TARGET=ui`) succeeded.
  Production API entrypoint ran as non-root on a configured port, passed readiness,
  and completed a streamed run against the isolated test database. UI runtime UID
  was also verified as non-root. Temporary verification containers were removed.
- Ruff lint/format checks and offline lockfile consistency check.

## Hosted checks still require configuration

- Hosted Pinecone: supply a Starter project API key; run the read-only smoke check.
- OpenAI: supply an API key; the provided smoke check lists models without generating text.
- LangSmith: supply a key/region, enable tracing, and run the trace smoke check.
  The check verifies two successes and one failure grouped by thread. Tracing
  code is present, but no upload to the user's account has been verified yet.
- No Railway resources, registry uploads, public URLs, DNS/TLS certificates, or
  remote backups were provisioned or tested. Remote deployment needs its own
  networking, streaming, and restore verification.

## Deliberate scope limits

The application has one mock node. It does not implement retrieval, an LLM answer,
RBAC/authentication, rate limiting, RLM research, or MCP yet. It supports one API
process, request-bound execution, and explicit checkpoint resume. It does not
provide background run recovery, atomic checkpoint/event writes, or exactly-once
tool side effects. The remote deployment files are preparation, not a claim that
the entire assignment is production-ready.
