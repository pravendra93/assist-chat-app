# -------------------------------
# Stage 1 — Builder
# -------------------------------
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /install

# Install system deps only for building
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --upgrade pip

# Copy requirements
COPY requirements.txt .

# Install into separate directory
RUN pip install --prefix=/install/deps --no-cache-dir -r requirements.txt


# -------------------------------
# Stage 2 — Final Image
# -------------------------------
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /code

# Copy installed dependencies from builder
COPY --from=builder /install/deps /usr/local

# Copy application code
COPY --chown=appuser:appuser ./app /code/app

# Create logs directory
RUN mkdir -p /code/logs && chown appuser:appuser /code/logs

USER appuser

# Minimal workers for 1GB server
CMD ["gunicorn", "app.main:app", "--workers", "2", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8001", "--timeout", "120", "--graceful-timeout", "30", "--keep-alive", "5" ]