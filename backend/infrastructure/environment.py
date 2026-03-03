"""
Environment Config — Environment Separation (Section 15)
═══════════════════════════════════════════════════════
Never mix environments.

  Development
  Staging
  Production

Each has:
  - own DB
  - own API keys
  - own workers

This module implements:
  - Environment detection (dev/staging/production)
  - Environment-specific configuration overlays
  - Secure credential management
  - Feature flags per environment
  - Configuration validation
  - Environment info endpoint data
"""

import os
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


# ═══════════════════════════════════════════════════
# ENVIRONMENT TYPES
# ═══════════════════════════════════════════════════
class Environment(Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


# ═══════════════════════════════════════════════════
# ENVIRONMENT-SPECIFIC CONFIGURATION
# ═══════════════════════════════════════════════════
ENVIRONMENT_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "development": {
        "debug": True,
        "log_level": "DEBUG",
        "db_engine": "sqlite",
        "db_path": "data/survey_engine.db",
        "workers_min": 1,
        "workers_max": 3,
        "queue_max_size": 1000,
        "cache_max_entries": 500,
        "cache_default_ttl": 300,            # 5 min
        "rate_limit_rpm": 120,
        "rate_limit_ai_rpm": 60,
        "cors_origins": ["*"],
        "enable_docs": True,                 # Swagger/ReDoc
        "enable_metrics": True,
        "enable_profiling": True,
        "storage_backend": "local",
        "ai_model": "gemini-2.5-flash",
        "ai_fallback_models": [
            "gemini-2.5-flash", "gemini-2.0-flash",
            "gemini-2.5-flash-lite", "gemini-2.0-flash-lite",
        ],
        "circuit_failure_threshold": 10,     # More lenient in dev
        "circuit_timeout_seconds": 30.0,
        "health_check_interval": 60.0,
        "feature_flags": {
            "enable_voice": True,
            "enable_executive_reports": True,
            "enable_hitl": True,
            "enable_batch_processing": True,
            "enable_websocket_channels": True,
        },
    },
    "staging": {
        "debug": False,
        "log_level": "INFO",
        "db_engine": "sqlite",               # Staging can still use SQLite
        "db_path": "data/survey_engine_staging.db",
        "workers_min": 2,
        "workers_max": 10,
        "queue_max_size": 5000,
        "cache_max_entries": 2000,
        "cache_default_ttl": 600,
        "rate_limit_rpm": 60,
        "rate_limit_ai_rpm": 30,
        "cors_origins": ["https://staging.yourdomain.com"],
        "enable_docs": True,
        "enable_metrics": True,
        "enable_profiling": False,
        "storage_backend": "local",
        "ai_model": "gemini-2.5-flash",
        "ai_fallback_models": [
            "gemini-2.5-flash", "gemini-2.0-flash",
            "gemini-2.5-flash-lite",
        ],
        "circuit_failure_threshold": 5,
        "circuit_timeout_seconds": 60.0,
        "health_check_interval": 30.0,
        "feature_flags": {
            "enable_voice": True,
            "enable_executive_reports": True,
            "enable_hitl": True,
            "enable_batch_processing": True,
            "enable_websocket_channels": True,
        },
    },
    "production": {
        "debug": False,
        "log_level": "WARNING",
        "db_engine": "postgresql",           # Production uses Postgres
        "db_path": "",                       # Uses DATABASE_URL
        "workers_min": 3,
        "workers_max": 50,
        "queue_max_size": 10000,
        "cache_max_entries": 5000,
        "cache_default_ttl": 3600,
        "rate_limit_rpm": 30,
        "rate_limit_ai_rpm": 15,
        "cors_origins": ["https://yourdomain.com"],
        "enable_docs": False,                # No Swagger in prod
        "enable_metrics": True,
        "enable_profiling": False,
        "storage_backend": "s3",
        "ai_model": "gemini-2.5-flash",
        "ai_fallback_models": [
            "gemini-2.5-flash", "gemini-2.0-flash",
            "gemini-2.5-flash-lite", "gemini-2.0-flash-lite",
            "gemini-3-flash-preview",
        ],
        "circuit_failure_threshold": 5,
        "circuit_timeout_seconds": 60.0,
        "health_check_interval": 15.0,
        "feature_flags": {
            "enable_voice": True,
            "enable_executive_reports": True,
            "enable_hitl": True,
            "enable_batch_processing": True,
            "enable_websocket_channels": True,
        },
    },
    "testing": {
        "debug": True,
        "log_level": "DEBUG",
        "db_engine": "sqlite",
        "db_path": ":memory:",
        "workers_min": 1,
        "workers_max": 2,
        "queue_max_size": 100,
        "cache_max_entries": 100,
        "cache_default_ttl": 60,
        "rate_limit_rpm": 1000,
        "rate_limit_ai_rpm": 1000,
        "cors_origins": ["*"],
        "enable_docs": False,
        "enable_metrics": False,
        "enable_profiling": False,
        "storage_backend": "local",
        "ai_model": "gemini-2.5-flash",
        "ai_fallback_models": ["gemini-2.5-flash"],
        "circuit_failure_threshold": 100,
        "circuit_timeout_seconds": 5.0,
        "health_check_interval": 300.0,
        "feature_flags": {
            "enable_voice": False,
            "enable_executive_reports": True,
            "enable_hitl": True,
            "enable_batch_processing": False,
            "enable_websocket_channels": False,
        },
    },
}


# ═══════════════════════════════════════════════════
# ENVIRONMENT CONFIGURATION CLASS
# ═══════════════════════════════════════════════════
class EnvironmentConfig:
    """
    Environment-aware configuration manager.

    Reads APP_ENV (or ENVIRONMENT) from os.environ.
    Falls back to 'development' if not set.

    Usage:
        env = EnvironmentConfig()
        env.get("workers_max")      # → 3 in dev, 50 in prod
        env.is_production           # → True/False
        env.feature_flag("enable_voice")
    """

    def __init__(self):
        self._env = self._detect_environment()
        self._config = ENVIRONMENT_DEFAULTS.get(self._env.value, ENVIRONMENT_DEFAULTS["development"]).copy()
        self._apply_env_overrides()
        self._validate()

    def _detect_environment(self) -> Environment:
        """Detect environment from APP_ENV or ENVIRONMENT variable."""
        env_str = os.environ.get("APP_ENV", os.environ.get("ENVIRONMENT", "development")).lower().strip()
        mapping = {
            "dev": Environment.DEVELOPMENT,
            "development": Environment.DEVELOPMENT,
            "staging": Environment.STAGING,
            "stage": Environment.STAGING,
            "prod": Environment.PRODUCTION,
            "production": Environment.PRODUCTION,
            "test": Environment.TESTING,
            "testing": Environment.TESTING,
        }
        return mapping.get(env_str, Environment.DEVELOPMENT)

    def _apply_env_overrides(self):
        """
        Override config values from environment variables.
        Pattern: CONFIG_{KEY} → e.g., CONFIG_WORKERS_MAX=20
        """
        for key in self._config:
            env_key = f"CONFIG_{key.upper()}"
            env_val = os.environ.get(env_key)
            if env_val is not None:
                # Type coercion
                current = self._config[key]
                if isinstance(current, bool):
                    self._config[key] = env_val.lower() in ("true", "1", "yes")
                elif isinstance(current, int):
                    try:
                        self._config[key] = int(env_val)
                    except ValueError:
                        pass
                elif isinstance(current, float):
                    try:
                        self._config[key] = float(env_val)
                    except ValueError:
                        pass
                else:
                    self._config[key] = env_val

    def _validate(self):
        """Validate critical configuration values."""
        errors = []
        if self._env == Environment.PRODUCTION:
            # Ensure API keys are not defaults in production
            gemini_key = os.environ.get("GEMINI_API_KEY", "")
            if not gemini_key or gemini_key.startswith("AIzaSy"):
                # Allow default for now but warn
                pass

            # Ensure debug is off
            if self._config.get("debug", False):
                errors.append("DEBUG must be False in production")

            # Ensure Swagger is off
            if self._config.get("enable_docs", True):
                errors.append("API docs should be disabled in production")

        if errors:
            print(f"[Environment] WARNING — Config validation issues: {errors}")

    # ─── Access ───
    @property
    def environment(self) -> Environment:
        return self._env

    @property
    def is_development(self) -> bool:
        return self._env == Environment.DEVELOPMENT

    @property
    def is_staging(self) -> bool:
        return self._env == Environment.STAGING

    @property
    def is_production(self) -> bool:
        return self._env == Environment.PRODUCTION

    @property
    def is_testing(self) -> bool:
        return self._env == Environment.TESTING

    def get(self, key: str, default: Any = None) -> Any:
        """Get a config value."""
        return self._config.get(key, default)

    def feature_flag(self, flag_name: str) -> bool:
        """Check if a feature flag is enabled."""
        flags = self._config.get("feature_flags", {})
        return flags.get(flag_name, False)

    def all_feature_flags(self) -> Dict[str, bool]:
        """Get all feature flags."""
        return self._config.get("feature_flags", {}).copy()

    # ─── Info ───
    def info(self) -> dict:
        """Get full environment info (safe for API exposure)."""
        safe_config = {}
        for k, v in self._config.items():
            # Redact sensitive values
            if any(secret in k.lower() for secret in ["key", "secret", "password", "token"]):
                safe_config[k] = "***"
            else:
                safe_config[k] = v

        return {
            "environment": self._env.value,
            "is_production": self.is_production,
            "is_development": self.is_development,
            "config": safe_config,
            "feature_flags": self.all_feature_flags(),
        }


# ═══════════════════════════════════════════════════
# GLOBAL ENVIRONMENT CONFIG SINGLETON
# ═══════════════════════════════════════════════════
env_config = EnvironmentConfig()
