FROM python:3.11

# Make Python output unbuffered, so logs are shown immediately
ENV PYTHONUNBUFFERED=1

# Install NTP client for clock synchronization verification
# NOTE: Docker containers inherit the host kernel clock via VDSO (Virtual Dynamic Shared Object).
# We do NOT run NTP synchronization inside containers - the host system must be NTP-synchronized.
# This package is kept for verification scripts only (e.g., verify_host_ntp.py).
# Best practice: Sync the host system with NTP, containers automatically inherit correct time.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ntpsec-ntpdate \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /tmp/* \
    && rm -rf /var/tmp/*

RUN pip install --upgrade pip

WORKDIR /app

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install dependencies with BuildKit cache mount (faster rebuilds, not in final image)
# Use --no-cache-dir to avoid storing pip cache in the image and save space
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r requirements.txt && \
    # Clean up any temporary files and Python bytecode caches to free space
    find /usr/local/lib/python3.11 -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true && \
    find /usr/local/lib/python3.11 -name "*.pyc" -delete 2>/dev/null || true && \
    find /usr/local/lib/python3.11 -name "*.pyo" -delete 2>/dev/null || true && \
    rm -rf /tmp/* /var/tmp/*

# Copy application code
COPY . .

# Copy .env if it exists (optional, may be provided via environment variables)
COPY .env* ./

EXPOSE 8080

CMD ["python", "src/app.py", "-v"]
