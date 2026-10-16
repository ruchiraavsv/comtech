ARG APP_TARGET=api
FROM ghcr.io/astral-sh/uv:0.12.19 AS uv
FROM python:3.12.14-slim-bookworm AS base
COPY --from=uv /uv /usr/local/bin/uv
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY src ./src

FROM base AS api
RUN uv sync --frozen --extra mcp --no-dev --no-editable && useradd --uid 10001 --create-home app
ENV TIKTOKEN_CACHE_DIR=/app/.cache/tiktoken
RUN .venv/bin/python -c "import tiktoken; tiktoken.get_encoding('cl100k_base'); tiktoken.get_encoding('o200k_base')"
ENV PATH="/app/.venv/bin:$PATH" PORT=8000 HOST=0.0.0.0
USER app
EXPOSE 8000
CMD ["python", "-m", "comtech.api"]

FROM base AS ui
RUN uv sync --frozen --no-dev --group ui --no-editable && useradd --uid 10001 --create-home app
COPY ui ./ui
ENV PATH="/app/.venv/bin:$PATH" PORT=8501
USER app
EXPOSE 8501
CMD ["python", "ui/start.py"]

FROM base AS test
RUN uv sync --frozen --extra mcp --extra research --group ui --no-editable
ENV TIKTOKEN_CACHE_DIR=/app/.cache/tiktoken
RUN .venv/bin/python -c "import tiktoken; tiktoken.get_encoding('cl100k_base'); tiktoken.get_encoding('o200k_base')"
COPY tests ./tests
COPY ui ./ui
COPY synthetic_bank/corpus ./synthetic_bank/corpus
COPY synthetic_bank/mcp/fixtures ./synthetic_bank/mcp/fixtures
CMD ["uv", "run", "--frozen", "--no-sync", "pytest", "-q"]

FROM python:3.12.14-slim-bookworm AS mcp
COPY --from=uv /uv /usr/local/bin/uv
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --only-group mcp-runtime --no-install-project && useradd --uid 10001 --create-home app
COPY src/comtech/__init__.py ./src/comtech/__init__.py
COPY src/comtech/mcp ./src/comtech/mcp
COPY synthetic_bank/mcp/fixtures ./synthetic_bank/mcp/fixtures
ENV PATH="/app/.venv/bin:$PATH" PYTHONPATH=/app/src NORTHSTAR_MCP_HOST=0.0.0.0 NORTHSTAR_MCP_PORT=8001
USER app
EXPOSE 8001
CMD ["python", "-m", "comtech.mcp"]

FROM mcp AS mcp-test
USER root
RUN uv sync --frozen --only-group mcp-runtime --only-group dev --no-install-project
COPY tests/__init__.py ./tests/__init__.py
COPY tests/mcp ./tests/mcp
USER app
CMD ["python", "-m", "pytest", "tests/mcp", "-q", "-p", "no:cacheprovider"]

FROM python:3.12.14-slim-bookworm AS runner-deps
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /opt/runner-build
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --only-group runner-runtime --no-install-project --no-editable

FROM python:3.12.14-slim-bookworm AS research-broker
COPY --from=uv /uv /usr/local/bin/uv
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --extra research --no-dev --no-install-project && useradd --uid 10000 --create-home broker
ENV TIKTOKEN_CACHE_DIR=/app/.cache/tiktoken
RUN .venv/bin/python -c "import tiktoken; tiktoken.get_encoding('cl100k_base'); tiktoken.get_encoding('o200k_base')"
COPY src/comtech/__init__.py src/comtech/db.py src/comtech/settings.py ./src/comtech/
COPY src/comtech/agents/__init__.py src/comtech/agents/budget.py src/comtech/agents/contracts.py src/comtech/agents/errors.py ./src/comtech/agents/
COPY src/comtech/research/__init__.py src/comtech/research/access.py src/comtech/research/accounting.py src/comtech/research/actions.py src/comtech/research/admission.py src/comtech/research/artifacts.py src/comtech/research/broker.py src/comtech/research/broker_contracts.py src/comtech/research/broker_schema.py src/comtech/research/budgets.py src/comtech/research/contracts.py src/comtech/research/delivery.py src/comtech/research/documents.py src/comtech/research/ledger.py src/comtech/research/operations.py src/comtech/research/python_execution.py src/comtech/research/queue.py src/comtech/research/queue_schema.py src/comtech/research/records.py src/comtech/research/replay.py src/comtech/research/runner_client.py src/comtech/research/runner_wire.py src/comtech/research/schema.py src/comtech/research/service.py src/comtech/research/transport.py ./src/comtech/research/
COPY src/comtech/retrieval ./src/comtech/retrieval
ENV PATH="/app/.venv/bin:$PATH" PYTHONPATH=/app/src
USER broker
CMD ["python", "-m", "comtech.research.service"]

FROM python:3.12.14-slim-bookworm AS python-runner
COPY --from=runner-deps /opt/runner-build/.venv /opt/venv
RUN rm -rf /usr/local/lib/python3.12/site-packages/pip* /usr/local/bin/pip* && \
    mkdir -p /run/research-control /opt/research && chown 10000:10000 /run/research-control && \
    chmod 700 /run/research-control
COPY src/comtech/research/data_sdk.py src/comtech/research/runner_wire.py src/comtech/research/sandbox.py src/comtech/research/runner_bootstrap.py src/comtech/research/runner.py /opt/research/
RUN /opt/venv/bin/python -c "import hashlib,json,sys,importlib.metadata,pathlib; p=pathlib.Path('/opt/research'); value={'python':sys.version,'packages':{n:importlib.metadata.version(n) for n in ['numpy','pandas','pyarrow','python-dateutil','six']},'modules':{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in p.glob('*.py')}}; (p/'environment.json').write_text(json.dumps(value,sort_keys=True))"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
USER 10000:10000
CMD ["/opt/venv/bin/python", "-I", "/opt/research/runner.py"]

# Railway passes APP_TARGET as a build argument; default is the API.
FROM ${APP_TARGET} AS runtime
