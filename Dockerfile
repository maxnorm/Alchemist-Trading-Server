FROM python:3.11

ENV PYTHONUNBUFFERED 1

workdir /app

COPY requirements.txt /app/

RUN pip install -r requirements.txt

COPY ./mt5-python_server /app


EXPOSE 8000
