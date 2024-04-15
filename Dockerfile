FROM python:3.10-slim

WORKDIR /code
ADD ./app ./app
RUN pip install --no-cache-dir --upgrade /code/.
