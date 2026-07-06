# syntax=docker/dockerfile:1
# ── Stage 1: build the React SPA (web/) ──────────────────────────────────────
# Produces web/dist, which the FastAPI app serves at / (same origin, no CORS).
# Node 22 satisfies Vite 8's engine requirement. node_modules is .dockerignored,
# so deps are installed fresh from the lockfile here, not copied from the host.
FROM node:22-slim AS web-build
WORKDIR /web

# Install deps in their own cached layer (keyed on the manifest + lock). The
# BuildKit cache mount keeps npm's download cache warm across rebuilds.
COPY web/package.json web/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci

# Build the bundle (tsc -b && vite build → web/dist).
COPY web/ ./
RUN npm run build

# ── Stage 2: Python runtime (FastAPI + core) ─────────────────────────────────
FROM python:3.11-slim

# uv binary (dependency manager)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# System deps: ffmpeg for the audio-transcription fallback.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# JS runtime for yt-dlp. Modern YouTube requires solving a JS challenge
# (signature deciphering + n-param) to produce valid, signed media URLs;
# without a runtime yt-dlp emits stale URLs and media downloads 403. deno is
# yt-dlp's default runtime (auto-detected on PATH — no extra config needed).
COPY --from=denoland/deno:bin /deno /usr/local/bin/deno

# Use the image's Python; don't let uv download its own. Put the project venv
# on PATH so `alembic`/`uvicorn` resolve directly in CMD.
ENV UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

# Install dependencies in their own cached layer (keyed on the manifest + lock).
# The BuildKit cache mount reuses uv's download/build cache across rebuilds.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen

# Application code: the FastAPI layer (api/) over the core library (merlin/).
COPY merlin/ ./merlin/
COPY api/ ./api/
COPY scripts/ ./scripts/
COPY alembic.ini ./

# The React SPA built in stage 1. api/main.py mounts this at / when present.
COPY --from=web-build /web/dist/ ./web/dist/

# Persistent dirs (mounted as volumes in compose)
RUN mkdir -p /app/logs /app/data

EXPOSE 8000

# Run migrations against the app DB (env.py reads DATABASE_URL), then serve the
# FastAPI app (which serves /api/* and, when built, the React SPA at /).
CMD ["sh", "-c", "alembic upgrade head && uvicorn api.main:app --host 0.0.0.0 --port 8000"]
