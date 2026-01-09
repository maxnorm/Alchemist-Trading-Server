FROM python:3.11

# Make Python output unbuffered, so logs are shown immediately
ENV PYTHONUNBUFFERED=1

# Install NTP client for clock synchronization
RUN apt-get update && apt-get install -y --no-install-recommends \
    ntpdate \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip

WORKDIR /app
COPY ./src/trading_server .

COPY .env .env

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8080

CMD ["python", "src/app.py", "-v"]
