FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.10 /uv /uvx /bin/

# rasterio's manylinux wheel links libexpat, which slim images omit
RUN apt-get update && apt-get install -y --no-install-recommends libexpat1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY app ./app

ENV PATH="/app/.venv/bin:$PATH"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
