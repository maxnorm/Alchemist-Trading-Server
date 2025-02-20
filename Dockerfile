FROM python:3.11

# Make Python output unbuffered, so logs are shown immediately
ENV PYTHONUNBUFFERED 1

RUN pip install --upgrade pip

WORKDIR /app
COPY ./src/mt5-python_server .

COPY .env .env

RUN pip install --no-cache-dir -r requirements.txt


EXPOSE 8080

CMD ["python", "src/app.py", "-v"]
