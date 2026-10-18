# Book Companion FastAPI image.
#
# Multi-stage build using uv for reproducible installs. Runs as a non-root user
# per security steering. Base image is python:3.11-slim (Python pinned to 3.11).

# ---- Builder: resolve and install dependencies into a venv ----
FROM python:3.11-slim AS builder

# uv provides fast, lockfile-based installs.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# Install dependencies first (cached layer) using only the lock + manifest.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Install the project itself.
COPY src ./src
COPY README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# ---- Runtime: minimal image, non-root ----
FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

# The runtime uses the self-contained uv venv (/app/.venv); the base image's
# system build tooling (pip/setuptools/wheel) is not needed at runtime and ships
# packages with HIGH CVEs the image scan flags (e.g. wheel, setuptools' vendored
# jaraco.context). Remove it so the runtime image stays clean.
RUN pip uninstall -y pip setuptools wheel 2>/dev/null || true; \
    find /usr/local/lib/python3.11/site-packages \
      \( -name 'setuptools*' -o -name 'wheel*' -o -name 'pip*' -o -name 'pkg_resources*' \) \
      -exec rm -rf {} + 2>/dev/null || true

# Create a non-root user to run the application.
RUN groupadd --system app && useradd --system --gid app --home /app app

WORKDIR /app

# Copy the resolved virtual environment and application source.
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --chown=app:app src ./src

USER app

EXPOSE 8000

# Gunicorn manages uvicorn workers for production. WEB_CONCURRENCY tunes workers.
CMD ["gunicorn", "src.main:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "2", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
