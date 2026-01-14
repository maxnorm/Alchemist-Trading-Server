FROM python:3.11

# Make Python output unbuffered, so logs are shown immediately
ENV PYTHONUNBUFFERED=1

# Install NTP client for clock synchronization
RUN apt-get update && apt-get install -y --no-install-recommends \
    ntpsec-ntpdate \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip

WORKDIR /app

# Copy requirements first for better layer caching
COPY ./src/trading_server/requirements.txt .

# Install dependencies with BuildKit cache mount (faster rebuilds, not in final image)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# Copy application code
COPY ./src/trading_server .

COPY .env .env

EXPOSE 8080

CMD ["python", "src/app.py", "-v"]
