FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    libmariadb-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/

# Set PYTHONPATH to include src directory for imports
ENV PYTHONPATH=/app/src

# Expose port
EXPOSE 8000

# Run the application (use main:app since PYTHONPATH points to src)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
