# Stage 1: Build
FROM python:3.11-slim AS builder

ENV PATH="/root/.local/bin:$PATH"
WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc python3-dev apt-utils && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python -m pip install --upgrade pip && \
    pip install --user --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/home/appuser/.local/bin:$PATH" \
    PYTHONPATH=/app
    # UVICORN_WORKERS will be handled by CMD's default shell expansion

WORKDIR /app

# Create a non-root user and group
RUN groupadd -r appgroup && useradd --no-log-init -r -g appgroup -d /home/appuser -s /sbin/nologin appuser && \
    mkdir -p /home/appuser/.local && chown -R appuser:appgroup /home/appuser && \
    touch /app/.env && \
    mkdir -p /app/logs && chown -R appuser:appgroup /app && \
    mkdir -p /app/static # Static files will be copied and owned by appuser later

# Copy installed packages from builder stage, adjust ownership
COPY --from=builder --chown=appuser:appgroup /root/.local /home/appuser/.local
# Copy application code, adjust ownership
COPY --chown=appuser:appgroup . .

USER appuser

EXPOSE 8100

# Use sh -c to allow shell expansion for default worker count
CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port 8100 --workers ${UVICORN_WORKERS:-4}"]
