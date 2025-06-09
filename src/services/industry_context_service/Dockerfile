FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y build-essential libpoppler-cpp-dev pkg-config poppler-utils \
                       libxml2-dev libxslt1-dev libjpeg-dev zlib1g-dev libglib2.0-0 \
                       libsm6 libxext6 libxrender-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /usr/src/app

# Copy requirements
COPY requirements.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY ./src .

# Download NLTK punkt (for sentence splitting, if needed)
RUN python -c "import nltk; nltk.download('punkt')"

# Expose port
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]