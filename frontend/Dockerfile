FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY frontend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY frontend .

# Expose Streamlit port
EXPOSE 8501

# Run the application
CMD ["streamlit", "run", "Home.py", "--server.address", "0.0.0.0"]
