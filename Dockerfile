FROM ghcr.io/astral-sh/uv:0.12.19 AS uv
FROM python:3.12.14-slim-bookworm AS base
COPY --from=uv /uv /usr/local/bin/uv
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY src ./src

FROM base AS api
RUN uv sync --frozen --no-dev --no-editable && useradd --uid 10001 --create-home app
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
RUN uv sync --frozen --no-editable
COPY tests ./tests
CMD ["uv", "run", "--frozen", "pytest", "-q"]
