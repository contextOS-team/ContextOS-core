# Stage 1: Install dependencies only
FROM python:3.12-slim AS builder

WORKDIR /app

COPY pyproject.toml .

# Install only the dependencies (not the package itself)
RUN pip install --no-cache-dir --upgrade pip \
    && mkdir -p src && touch src/__init__.py \
    && pip install --no-cache-dir .

# Stage 2: Production image
FROM python:3.12-slim AS production

WORKDIR /app

RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid 1000 --shell /bin/bash appuser

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application source
COPY src/ ./src/

USER appuser

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
