# syntax=docker/dockerfile:1.7
FROM python:3.11-slim

WORKDIR /project/backend

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml backend/README.md ./
COPY backend/app ./app
COPY backend/cli ./cli
COPY marketplace.example.yaml /project/marketplace.example.yaml

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -e ".[dev]"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
