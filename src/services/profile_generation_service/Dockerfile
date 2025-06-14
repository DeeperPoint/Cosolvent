# ./src/services/user_management_service/Dockerfile
FROM python:3.11-slim

# 1. Copy & install the shared library
COPY src/shared /opt/shared
WORKDIR /opt/shared
RUN pip install --no-cache-dir -e .

 # 2. Set up service directory and install dependencies (cache pip layer unless requirements change)
 WORKDIR /opt/service
 COPY src/services/profile_generation_service/requirements.txt ./requirements.txt
 RUN pip install --no-cache-dir -r requirements.txt
 # Copy service code
 COPY src/services/profile_generation_service /opt/service
ENV PYTHONPATH=/opt/service

CMD ["python", "-u", "-m", "src.utils.profile_consumer"]