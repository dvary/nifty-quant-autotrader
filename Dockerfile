FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create data directory for persistence
RUN mkdir -p /app/data/logs

# Copy and install python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files (Copy everything except what is in .dockerignore)
COPY . .

# Set Python path to ensure imports work correctly
ENV PYTHONPATH=/app

# Expose port for FastAPI
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--env-file", ".env"]
