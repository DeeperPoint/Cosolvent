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

# Runtime image installs ONLY runtime deps. Dev tools (pytest, ruff, mypy,
# pre-commit, etc.) belong in the host venv (``backend/.venv``) and never
# need to ship in the container. Stripping them avoids ~50 MB of wheels
# (notably pre-commit → virtualenv) that previously failed the build on
# slow networks. ``--timeout`` + ``--retries`` give pip enough rope to
# survive transient PyPI hiccups.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --timeout=180 --retries=5 -e "."

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
