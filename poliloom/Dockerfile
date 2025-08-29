FROM ghcr.io/astral-sh/uv:python3.12-bookworm AS builder

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

FROM python:3.12-slim AS runtime


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
RUN chown -R poliloom:poliloom /app
USER poliloom

# Expose port
EXPOSE 8000

# Set default port
ENV PORT=8000

# Default command - use PORT environment variable
CMD ["sh", "-c", "uvicorn poliloom.api.app:app --host 0.0.0.0 --port $PORT"]
