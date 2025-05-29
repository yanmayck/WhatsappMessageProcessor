# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Create a virtual environment
RUN python -m venv /opt/venv
# Activate virtual environment
ENV PATH="/opt/venv/bin:$PATH"

# Copy dependency definition files
COPY pyproject.toml uv.lock* ./
# uv.lock* para incluir uv.lock se ele existir.
# Se você não usar uv.lock, apenas pyproject.toml.

# Install dependencies
# Usando pip install . para instalar a partir do pyproject.toml
# --no-cache-dir é bom para manter a imagem menor
RUN pip install --no-cache-dir .

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