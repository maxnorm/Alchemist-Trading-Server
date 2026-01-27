# Multi-stage build to reduce final image size
# Stage 1: Build dependencies
FROM python:3.11-slim as builder

# Install build dependencies needed for compiling Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    libc6-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Upgrade pip
RUN pip install --upgrade pip

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install dependencies with BuildKit cache mount
# Use --no-cache-dir to avoid storing pip cache in the image
# Install to /usr/local (default) for better compatibility
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r requirements.txt && \
    # Clean up Python bytecode caches immediately
    find /usr/local/lib/python3.11 -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true && \
    find /usr/local/lib/python3.11 -name "*.pyc" -delete 2>/dev/null || true && \
    find /usr/local/lib/python3.11 -name "*.pyo" -delete 2>/dev/null || true

# Stage 2: Runtime image (much smaller - no build tools)
FROM python:3.11-slim

# Make Python output unbuffered, so logs are shown immediately
ENV PYTHONUNBUFFERED=1

# Install only runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ntpsec-ntpdate \
    # Runtime libraries that might be needed by compiled packages
    libgomp1 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /tmp/* \
    && rm -rf /var/tmp/*

WORKDIR /app

# Copy installed Python packages from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
# Build context is src/backend/trading_server, so src/ contains app.py
COPY src/ ./src/
COPY requirements.txt ./

# Copy .env if it exists (optional, may be provided via environment variables)
COPY .env* ./

EXPOSE 8080

# Verify app.py exists at the expected location
RUN test -f /app/src/app.py || (echo "ERROR: /app/src/app.py not found!" && find /app -name "app.py" -type f 2>/dev/null | head -5 && exit 1)

CMD ["python", "/app/src/app.py", "-v"]
