FROM ubuntu:24.04 AS builder

RUN apt-get update && apt-get install -y python3 python3-pip && rm -rf /var/lib/apt/lists/*
RUN pip3 install --break-system-packages uv

# Set environment variables for optimal uv behavior
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Set working directory
WORKDIR /app

# Install all dependencies first with CPU-only PyTorch
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    uv sync --frozen --no-install-project --no-dev --extra cpu

# Copy package source and setup files
COPY pyproject.toml ./
COPY README.md ./
COPY poliloom/ ./poliloom/

# Install the package without dependencies (already installed)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install . --no-deps

FROM ubuntu:24.04 AS runtime

RUN apt-get update && apt-get install -y python3 && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy virtual environment from builder stage (includes installed package)
COPY --from=builder /app/.venv /app/.venv

# Copy alembic configuration from builder stage
COPY alembic.ini /app/
COPY alembic/ /app/alembic/

# Add virtual environment to PATH
ENV PATH="/app/.venv/bin:$PATH"

# Create non-root user
RUN groupadd -r poliloom && useradd -r -g poliloom poliloom
# Create cache directories with correct ownership
RUN mkdir -p /var/cache/wikidata /var/cache/huggingface /var/cache/playwright && \
    chown -R poliloom:poliloom /var/cache/wikidata /var/cache/huggingface /var/cache/playwright

# Install Playwright browsers as root, then fix ownership
ENV PLAYWRIGHT_BROWSERS_PATH=/var/cache/playwright
RUN /app/.venv/bin/playwright install --with-deps chromium
RUN chown -R poliloom:poliloom /app /var/cache/playwright

# Switch to poliloom user
USER poliloom

# Expose port
EXPOSE 8000

# Set default port and workers
ENV PORT=8000
ENV WORKERS=8

# Default command - use PORT and WORKERS environment variables
CMD ["sh", "-c", "uvicorn poliloom.api:app --host 0.0.0.0 --port $PORT --workers $WORKERS"]
