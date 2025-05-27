FROM python:3.11-slim


COPY ../../shared /opt/shared
WORKDIR /opt/shared
RUN pip install --no-cache-dir -e .

WORKDIR /opt/service
COPY . .
