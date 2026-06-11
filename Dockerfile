FROM python:3.11-slim

# uv binary (dependency manager)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# System deps: ffmpeg for the audio-transcription fallback.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Use the image's Python; don't let uv download its own. Put the project venv
# on PATH so `alembic`/`streamlit` resolve directly in CMD.
ENV UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

# Install dependencies in their own cached layer (keyed on the manifest + lock).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

# Application code (core library + Streamlit UI + entry point)
COPY merlin/ ./merlin/
COPY ui/ ./ui/
COPY app.py alembic.ini ./
COPY scripts/ ./scripts/

# Persistent dirs (mounted as volumes in compose)
RUN mkdir -p /app/logs /app/data

EXPOSE 8501

# Run migrations against the app DB (env.py reads DATABASE_URL), then serve.
CMD ["sh", "-c", "alembic upgrade head && streamlit run app.py --server.port 8501 --server.address 0.0.0.0 --server.headless true"]
