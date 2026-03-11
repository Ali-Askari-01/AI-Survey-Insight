# ═══════════════════════════════════════════════════
# Dockerfile — AI Survey Software Backend
# Optimized for Railway Deployment
# ═══════════════════════════════════════════════════
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install (cached layer — changes rarely)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY gunicorn.conf.py .

# Create data directories (Railway volume mounts over /app/data if configured)
RUN mkdir -p /app/data /app/data/storage /app/data/backups /app/logs

# Environment variables — Railway injects secrets at runtime
ENV PYTHONUNBUFFERED=1
ENV APP_ENV=production
ENV WORKERS=2
ENV PORT=8000

# Expose port (Railway overrides via $PORT)
EXPOSE ${PORT}

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Production: Gunicorn with Uvicorn workers
CMD ["gunicorn", "-c", "gunicorn.conf.py", "backend.main:app"]
