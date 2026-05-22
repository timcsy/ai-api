# syntax=docker/dockerfile:1.7

# --- builder ---
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    cp /root/.local/bin/uv /usr/local/bin/uv

COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN uv pip install --system --no-cache .

# --- runtime: distroless ---
# Pinned to a known-good digest. Bump via Renovate (PR + Trivy gate).
FROM gcr.io/distroless/python3-debian12:nonroot AS runtime

WORKDIR /app

# Copy site-packages + entrypoint scripts from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn
COPY --from=builder /usr/local/bin/alembic /usr/local/bin/alembic

# distroless `python3` lives at /usr/bin/python3.11 with sys.path NOT including
# /usr/local/lib/python3.11/site-packages by default. Export it so installed packages
# are discoverable.
ENV PYTHONPATH=/usr/local/lib/python3.11/site-packages \
    PATH=/usr/local/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY deploy/docker/healthcheck.py /app/healthcheck.py

USER nonroot

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=5s --retries=5 \
    CMD ["python3", "/app/healthcheck.py"]

ENTRYPOINT ["python3"]
CMD ["-m", "uvicorn", "ai_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
