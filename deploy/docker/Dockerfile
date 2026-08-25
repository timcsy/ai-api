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

# Deterministic, dependencies-ONLY install pinned from uv.lock (NOT pyproject
# ranges) and EXCLUDING the project itself (--no-emit-project). Two payoffs:
#   1. reproducible — the resolved dep set is fixed by the lock, so the same
#      commit always yields the same site-packages bytes;
#   2. cache-stable — this ~1GB layer's inputs are only pyproject.toml + uv.lock,
#      so a code-only change does NOT rebuild it and cluster nodes reuse the
#      already-pulled layer (no slow multi-minute re-pull → no helm hook timeout).
# The project code itself is NOT installed here; it ships as /app/src and runs
# via PYTHONPATH in the runtime stage (a separate, tiny layer).
COPY pyproject.toml uv.lock README.md ./
RUN uv export --frozen --no-dev --no-emit-project -o /tmp/requirements.txt && \
    uv pip install --system --no-cache -r /tmp/requirements.txt

# --- runtime: distroless ---
# Pinned to a known-good digest. Bump via Renovate (PR + Trivy gate).
FROM gcr.io/distroless/python3-debian12:nonroot AS runtime

WORKDIR /app

# Dependencies (stable layer — changes only when uv.lock changes).
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn
COPY --from=builder /usr/local/bin/alembic /usr/local/bin/alembic

# distroless `python3` lives at /usr/bin/python3.11 with sys.path NOT including
# our paths by default. Put the project source (/app/src) FIRST so `ai_api` is
# imported from the small code layer, then the deps in site-packages. Everything
# is invoked as `python3 -m …` (uvicorn / alembic / ai_api.cli.*), so no reliance
# on console-script shebangs.
ENV PYTHONPATH=/app/src:/usr/local/lib/python3.11/site-packages \
    PATH=/usr/local/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Project code — its own small layer (changes on every code edit, but it's tiny).
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
