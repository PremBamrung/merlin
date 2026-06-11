FROM python:3.11-slim

WORKDIR /app

# System deps: ffmpeg for the audio-transcription fallback; gcc/python3-dev for
# any packages that build from source.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install pinned dependencies (exported from uv: `uv export > requirements.docker.txt`)
COPY requirements.docker.txt ./
RUN pip install --no-cache-dir -r requirements.docker.txt

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
