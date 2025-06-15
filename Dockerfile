# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install build dependencies for psycopg2 and FFmpeg
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    ffmpeg \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Create and activate a virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip and setuptools first
RUN pip install --upgrade pip setuptools wheel

# Copy requirements file and install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# EXPOSE não é estritamente necessário para Cloud Run, pois ele usa a variável PORT,
# mas é uma boa documentação.
EXPOSE 8080

# Run app.py when the container launches using Gunicorn
# Cloud Run define a variável de ambiente PORT.
# Usar exec para que Gunicorn seja o processo PID 1.
# --timeout 0 para desabilitar o timeout do worker do Gunicorn (Cloud Run gerencia timeouts).
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 main:app 