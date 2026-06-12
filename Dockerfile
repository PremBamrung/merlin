FROM python:3.11-slim

# uv binary (dependency manager)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# System deps: ffmpeg for the audio-transcription fallback.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Use the image's Python; don't let uv download its own. Put the project venv
# on PATH so `alembic`/`uvicorn`/`streamlit` resolve directly in CMD.
ENV UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

# Install dependencies in their own cached layer (keyed on the manifest + lock).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

# Application code. The FastAPI layer (api/) and the core library (merlin/) are
# the v3 runtime; streamlit/ is the archived "engine room" (still runnable via
# the `streamlit` compose profile). The built React SPA (web/dist) is mounted by
# api/ at / when present — add a `COPY web/dist/ ./web/dist/` line once it exists.
COPY merlin/ ./merlin/
COPY api/ ./api/
COPY streamlit/ ./streamlit/
COPY scripts/ ./scripts/
COPY alembic.ini ./

# Persistent dirs (mounted as volumes in compose)
RUN mkdir -p /app/logs /app/data

EXPOSE 8000

# Run migrations against the app DB (env.py reads DATABASE_URL), then serve the
# FastAPI app (which serves /api/* and, when built, the React SPA at /).
CMD ["sh", "-c", "alembic upgrade head && uvicorn api.main:app --host 0.0.0.0 --port 8000"]
