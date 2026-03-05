"""
Configuration — API keys, security settings, and architecture config
All secrets are loaded from environment variables (see .env file).
"""
import os
import secrets
from dotenv import load_dotenv

# Load .env file (finds it automatically from project root)
load_dotenv()

# ── API Keys (loaded from .env — no hardcoded fallbacks) ──
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
ASSEMBLYAI_API_KEY = os.environ.get("ASSEMBLYAI_API_KEY", "")

if not GEMINI_API_KEY:
    print("⚠️  WARNING: GEMINI_API_KEY not set. AI features will not work. Add it to your .env file.")
if not ASSEMBLYAI_API_KEY:
    print("⚠️  WARNING: ASSEMBLYAI_API_KEY not set. Audio transcription will not work. Add it to your .env file.")

# ── Model settings ──
GEMINI_MODEL = "gemini-2.5-flash"

# ── JWT Authentication ──
JWT_SECRET = os.environ.get("JWT_SECRET", secrets.token_hex(32))
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# ── Google OAuth 2.0 ──
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.environ.get("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/auth/google/callback")

if not GOOGLE_CLIENT_ID:
    print("⚠️  WARNING: GOOGLE_CLIENT_ID not set. Google Sign-In will not work.")

# ═══════════════════════════════════════════════════
# ARCHITECTURE: Rate Limiting Configuration
# ═══════════════════════════════════════════════════
RATE_LIMIT_REQUESTS_PER_MINUTE = int(os.environ.get("RATE_LIMIT_RPM", "120"))
RATE_LIMIT_AI_REQUESTS_PER_MINUTE = int(os.environ.get("RATE_LIMIT_AI_RPM", "30"))
RATE_LIMIT_BURST_SIZE = int(os.environ.get("RATE_LIMIT_BURST", "15"))
RATE_LIMIT_AUTH_LOGIN_PER_MINUTE = int(os.environ.get("RATE_LIMIT_AUTH_LOGIN", "5"))
RATE_LIMIT_AUTH_REGISTER_PER_MINUTE = int(os.environ.get("RATE_LIMIT_AUTH_REGISTER", "3"))
MAX_FAILED_LOGIN_ATTEMPTS = int(os.environ.get("MAX_FAILED_LOGIN_ATTEMPTS", "5"))
FAILED_LOGIN_LOCKOUT_MINUTES = int(os.environ.get("FAILED_LOGIN_LOCKOUT_MINUTES", "15"))

# ═══════════════════════════════════════════════════
# ARCHITECTURE: Data Anonymization
# ═══════════════════════════════════════════════════
ANONYMIZE_RESPONSES = os.environ.get("ANONYMIZE_RESPONSES", "false").lower() == "true"

# ═══════════════════════════════════════════════════
# ARCHITECTURE: AI Orchestrator Settings
# ═══════════════════════════════════════════════════
AI_CACHE_MAX_SIZE = int(os.environ.get("AI_CACHE_MAX_SIZE", "200"))
AI_CACHE_TTL_SECONDS = int(os.environ.get("AI_CACHE_TTL", "3600"))
AI_MAX_BACKGROUND_WORKERS = int(os.environ.get("AI_MAX_WORKERS", "2"))

# ═══════════════════════════════════════════════════
# ARCHITECTURE: Observability
# ═══════════════════════════════════════════════════
ENABLE_METRICS = os.environ.get("ENABLE_METRICS", "true").lower() == "true"
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

# ═══════════════════════════════════════════════════
# EMAIL NOTIFICATIONS (Optional SMTP)
# ═══════════════════════════════════════════════════
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM_EMAIL = os.environ.get("SMTP_FROM_EMAIL", "")
SMTP_FROM_NAME = os.environ.get("SMTP_FROM_NAME", "AI Survey Platform")
SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "true").lower() == "true"

# ═══════════════════════════════════════════════════
# AI PROCESSING ARCHITECTURE: Smart Triggering
# ═══════════════════════════════════════════════════
INTELLIGENCE_RESPONSE_THRESHOLD = int(os.environ.get("INTEL_RESPONSE_THRESHOLD", "10"))
INTELLIGENCE_SENTIMENT_SHIFT_THRESHOLD = float(os.environ.get("INTEL_SENTIMENT_SHIFT", "0.3"))
INTELLIGENCE_INSIGHT_THRESHOLD = int(os.environ.get("INTEL_INSIGHT_THRESHOLD", "5"))
INTELLIGENCE_MIN_INTERVAL_SECONDS = int(os.environ.get("INTEL_MIN_INTERVAL", "60"))
INTELLIGENCE_BATCH_SIZE = int(os.environ.get("INTEL_BATCH_SIZE", "100"))

# ═══════════════════════════════════════════════════
# DATABASE BACKUP
# ═══════════════════════════════════════════════════
BACKUP_MAX_COUNT = int(os.environ.get("BACKUP_MAX_COUNT", "7"))
BACKUP_INTERVAL_HOURS = int(os.environ.get("BACKUP_INTERVAL_HOURS", "24"))

# ═══════════════════════════════════════════════════
# FILE LOGGING
# ═══════════════════════════════════════════════════
LOG_MAX_SIZE_MB = int(os.environ.get("LOG_MAX_SIZE_MB", "10"))
LOG_BACKUP_COUNT = int(os.environ.get("LOG_BACKUP_COUNT", "5"))

# ═══════════════════════════════════════════════════
# POSTGRESQL MIGRATION (optional)
# ═══════════════════════════════════════════════════
DATABASE_URL = os.environ.get("DATABASE_URL", "")  # Set to postgresql://... to switch
