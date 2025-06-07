# ./src/services/user_management_service/Dockerfile
FROM python:3.11-slim

# 1. Copy & install the shared library
COPY src/shared /opt/shared
WORKDIR /opt/shared
RUN pip install --no-cache-dir -e .

# 2. Copy & install the service
COPY src/services/asset_service /opt/service
WORKDIR /opt/service
RUN pip install cache -r requirements.txt

RUN chmod +x /opt/service/entrypoint.sh
ENTRYPOINT ["/opt/service/entrypoint.sh"]

