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
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip

WORKDIR /app

# Copy requirements first for better layer caching
COPY ./src/backend/trading_server/requirements.txt .

# Install dependencies with BuildKit cache mount (faster rebuilds, not in final image)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# Copy application code
COPY ./src/backend/trading_server .

COPY .env .env

EXPOSE 8080

CMD ["python", "src/app.py", "-v"]
