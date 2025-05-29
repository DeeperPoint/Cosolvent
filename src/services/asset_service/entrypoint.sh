#!/bin/sh
# Wait for MongoDB and MinIO to be ready (add appropriate wait logic or use dockerize)
# e.g. sleep 10
exec uvicorn src.main:app --host 0.0.0.0 --port 8002
