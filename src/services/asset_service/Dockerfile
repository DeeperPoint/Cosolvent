# ./src/services/user_management_service/Dockerfile
FROM python:3.11-slim

# 1. Copy & install the shared library
COPY src/shared /opt/shared
WORKDIR /opt/shared
RUN pip install --no-cache-dir -e .

 # 2. Copy only requirements and install (cache pip layers unless requirements change)
 COPY src/services/asset_service/requirements.txt /opt/service/requirements.txt
 WORKDIR /opt/service
 RUN pip install --no-cache-dir -r requirements.txt
 # Copy service code
 COPY src/services/asset_service /opt/service

RUN chmod +x /opt/service/entrypoint.sh
ENTRYPOINT ["/opt/service/entrypoint.sh"]

