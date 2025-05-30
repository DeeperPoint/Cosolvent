# Dockerfile for LLM Orchestration Service

# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container at /app
# Specifically, copy the src directory and config.json
COPY ./src ./src
COPY config.json .

# Make port 80 available to the world outside this container
EXPOSE 8000

# Define environment variable (optional, can be set at runtime)
# ENV NAME World

# Run app.py when the container launches
# CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]

# If you have an entrypoint.sh script, you might use that instead:
# COPY entrypoint.sh /app/entrypoint.sh
# RUN chmod +x /app/entrypoint.sh
# ENTRYPOINT ["/app/entrypoint.sh"]

# For simple uvicorn startup:
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
