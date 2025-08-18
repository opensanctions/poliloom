FROM python:3.12-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install all dependencies first with CPU-only PyTorch
RUN uv sync --frozen --no-install-project --no-dev --extra cpu

# Copy application code
COPY . .

# Install the package in the virtual environment
RUN uv pip install .

FROM python:3.12-slim AS runtime


# Set working directory
WORKDIR /app

# Copy virtual environment from builder stage (includes installed package)
COPY --from=builder /app/.venv /app/.venv

# Add virtual environment to PATH
ENV PATH="/app/.venv/bin:$PATH"

# Create non-root user
RUN groupadd -r poliloom && useradd -r -g poliloom poliloom
RUN chown -R poliloom:poliloom /app
USER poliloom

# Expose port
EXPOSE 8000

# Default command
CMD ["uvicorn", "poliloom.api.app:app", "--host", "0.0.0.0", "--port", "8000"]