FROM python:3.11-slim

WORKDIR /code
ADD ./pyproject.toml ./pyproject.toml
RUN pip install --upgrade pip && pip install --no-cache-dir .
ADD ./app ./app

WORKDIR /code/app
