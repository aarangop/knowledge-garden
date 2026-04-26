FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install external dependencies first (layer-cache friendly)
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy source and install the local package
COPY src/ ./src/
RUN uv sync --frozen --no-dev

ENV PYTHONPATH=/app/src

CMD [".venv/bin/uvicorn", "knowledge_garden.main:app", "--host", "0.0.0.0", "--port", "8000"]
