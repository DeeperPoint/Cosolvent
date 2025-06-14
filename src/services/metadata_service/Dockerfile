# ./src/services/user_management_service/Dockerfile
FROM python:3.11-slim

# 1. Copy & install the shared library
COPY src/shared /opt/shared
WORKDIR /opt/shared
RUN pip install --no-cache-dir -e .

# 2. Copy & install the service

COPY src/services/metadata_service /opt/service
WORKDIR /opt/service

 # 3. Copy only requirements and install (cache unless changed)
 COPY src/services/metadata_service/requirements.txt /opt/service/requirements.txt
 RUN pip install --no-cache-dir -r requirements.txt
 # Copy service code
 COPY src/services/metadata_service /opt/service
ENV PYTHONPATH=/opt/service

CMD ["python", "-u", "-m", "src.utils.asset_consumer"]