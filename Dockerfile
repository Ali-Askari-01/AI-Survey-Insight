# ═══════════════════════════════════════════════════
# Dockerfile — AI Survey Software Backend
# Infrastructure & Scalability Architecture (Section 5)
# ═══════════════════════════════════════════════════
# Production: Gunicorn + Uvicorn Workers
#   gunicorn -k uvicorn.workers.UvicornWorker main:app
# Workers allow: ✅ parallel requests ✅ concurrency ✅ stability
# ═══════════════════════════════════════════════════
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY gunicorn.conf.py .

# Create data and storage directories
RUN mkdir -p /app/data /app/data/storage /app/data/backups

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV APP_ENV=production
ENV GEMINI_API_KEY=""
ENV ASSEMBLYAI_API_KEY=""
ENV JWT_SECRET=""
ENV WORKERS=4

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Production: Gunicorn with Uvicorn workers
CMD ["gunicorn", "-c", "gunicorn.conf.py", "backend.main:app"]
