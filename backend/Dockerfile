FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install backend dependencies first
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Merlin package
COPY merlin /app/merlin
RUN cd /app/merlin && pip install -e .

# Copy backend application code
COPY backend /app/backend

# Set Python path to include app directory
ENV PYTHONPATH=/app

# Expose FastAPI port
EXPOSE 8000

# Run the application with uvicorn
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
