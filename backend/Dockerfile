# Stage 1: Install dependencies only
FROM python:3.12-slim AS builder

WORKDIR /app

# Install uv for fast dependency resolution
RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./

# Install dependencies from the lockfile so prod resolution matches dev exactly.
# Without this, transitive deps drift (e.g. tree-sitter-language-pack jumped from
# 0.13.0 to a broken 1.6.3 stub). uv export emits a flat requirements.txt that pip
# can install into the system Python, preserving the existing layer-copy layout
# in stage 2.
RUN uv export --frozen --no-dev --no-emit-project --format requirements-txt \
        --output-file /tmp/requirements.txt \
    && uv pip install --system --no-cache --requirement /tmp/requirements.txt

# Stage 2: Production image
FROM python:3.12-slim AS production

WORKDIR /app

# git is required at runtime: code_indexer.py shells out to `git clone` to
# pull GitHub/GitLab repos for indexing. Without it, every clone fails with
# FileNotFoundError and indexing produces zero chunks.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid 1000 --shell /bin/bash appuser

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application source
COPY src/ ./src/

USER appuser

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
