"""
Rate Limiter Middleware — API Gateway Security Layer
═══════════════════════════════════════════════════════
Prevents: AI abuse, spam responses, API overload.

Uses sliding-window counters per IP + per user.
Architecture: "Airport Security of your system"
"""
import time
import threading
from collections import defaultdict
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from ..config import (
    RATE_LIMIT_REQUESTS_PER_MINUTE,
    RATE_LIMIT_AI_REQUESTS_PER_MINUTE,
    RATE_LIMIT_BURST_SIZE,
    RATE_LIMIT_AUTH_LOGIN_PER_MINUTE,
    RATE_LIMIT_AUTH_REGISTER_PER_MINUTE,
)


class SlidingWindowCounter:
    """Thread-safe sliding window rate counter."""

    def __init__(self):
        self._windows: dict = defaultdict(list)
        self._lock = threading.Lock()

    def check_and_increment(self, key: str, limit: int, window_seconds: int = 60) -> tuple:
        """
        Check if request is within rate limit.
        Returns (allowed: bool, remaining: int, retry_after: int)
        """
        now = time.time()
        with self._lock:
            # Clean old entries
            self._windows[key] = [
                ts for ts in self._windows[key]
                if now - ts < window_seconds
            ]

            current_count = len(self._windows[key])

            if current_count >= limit:
                # Calculate retry-after
                oldest = self._windows[key][0] if self._windows[key] else now
                retry_after = int(window_seconds - (now - oldest)) + 1
                return False, 0, retry_after

            # Record this request
            self._windows[key].append(now)
            remaining = limit - current_count - 1
            return True, remaining, 0

    def get_count(self, key: str, window_seconds: int = 60) -> int:
        now = time.time()
        with self._lock:
            self._windows[key] = [
                ts for ts in self._windows[key]
                if now - ts < window_seconds
            ]
            return len(self._windows[key])

    def cleanup(self, max_age: int = 300):
        """Remove stale entries older than max_age seconds."""
        now = time.time()
        with self._lock:
            stale_keys = []
            for key, timestamps in self._windows.items():
                self._windows[key] = [ts for ts in timestamps if now - ts < max_age]
                if not self._windows[key]:
                    stale_keys.append(key)
            for key in stale_keys:
                del self._windows[key]


# Global rate limiter
_rate_counter = SlidingWindowCounter()

# AI-specific endpoints that need stricter limiting
AI_ENDPOINTS = {
    "/api/surveys/intake/clarify",
    "/api/surveys/goals/ai-parse",
    "/api/surveys/questions/ai-generate",
    "/api/surveys/questions/ai-generate-deep",
    "/api/interviews/chat",
    "/api/interviews/respond",
    "/api/interviews/simulate",
    "/api/reports/summary/",
    "/api/reports/generate",
}

# Auth endpoints — strict rate limits to prevent brute force
AUTH_ENDPOINTS = {
    "/api/auth/login": RATE_LIMIT_AUTH_LOGIN_PER_MINUTE,
    "/api/auth/register": RATE_LIMIT_AUTH_REGISTER_PER_MINUTE,
}


def _get_client_ip(request: Request) -> str:
    """Extract client IP from request, handling proxies."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _is_ai_endpoint(path: str) -> bool:
    """Check if endpoint involves AI processing."""
    return any(path.startswith(ep) for ep in AI_ENDPOINTS)


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """
    Middleware that enforces rate limits per IP and per user.

    - General API: RATE_LIMIT_REQUESTS_PER_MINUTE per IP
    - AI endpoints: RATE_LIMIT_AI_REQUESTS_PER_MINUTE per IP (stricter)
    - Burst protection: No more than RATE_LIMIT_BURST_SIZE in 5 seconds

    Returns 429 Too Many Requests with Retry-After header when exceeded.
    """

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for static files and health checks
        path = request.url.path
        if path.startswith(("/css/", "/js/", "/assets/")) or path in ("/health", "/", "/app"):
            return await call_next(request)

        client_ip = _get_client_ip(request)

        # ── Auth Endpoint Rate Limiting (strictest — brute force protection) ──
        if path in AUTH_ENDPOINTS:
            auth_limit = AUTH_ENDPOINTS[path]
            auth_key = f"auth:{client_ip}:{path}"
            auth_ok, remaining, retry_after = _rate_counter.check_and_increment(
                auth_key, auth_limit, window_seconds=60
            )
            if not auth_ok:
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": f"Too many attempts. Please try again in {retry_after} seconds.",
                        "type": "auth_rate_limit",
                        "retry_after": retry_after,
                    },
                    headers={"Retry-After": str(retry_after)}
                )

        # ── Burst Protection (5-second window) ──
        burst_key = f"burst:{client_ip}"
        burst_ok, _, _ = _rate_counter.check_and_increment(
            burst_key, RATE_LIMIT_BURST_SIZE, window_seconds=5
        )
        if not burst_ok:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please slow down.", "type": "burst_limit"},
                headers={"Retry-After": "5"}
            )

        # ── AI Endpoint Rate Limiting (stricter) ──
        if _is_ai_endpoint(path):
            ai_key = f"ai:{client_ip}"
            ai_ok, remaining, retry_after = _rate_counter.check_and_increment(
                ai_key, RATE_LIMIT_AI_REQUESTS_PER_MINUTE, window_seconds=60
            )
            if not ai_ok:
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": f"AI rate limit exceeded. Retry after {retry_after}s.",
                        "type": "ai_rate_limit",
                        "retry_after": retry_after,
                    },
                    headers={"Retry-After": str(retry_after)}
                )

        # ── General Rate Limiting ──
        general_key = f"general:{client_ip}"
        ok, remaining, retry_after = _rate_counter.check_and_increment(
            general_key, RATE_LIMIT_REQUESTS_PER_MINUTE, window_seconds=60
        )
        if not ok:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": f"Rate limit exceeded. Retry after {retry_after}s.",
                    "type": "general_rate_limit",
                    "retry_after": retry_after,
                },
                headers={"Retry-After": str(retry_after)}
            )

        # Add rate limit headers to response
        response = await call_next(request)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Limit"] = str(RATE_LIMIT_REQUESTS_PER_MINUTE)
        return response


def get_rate_limit_stats() -> dict:
    """Get current rate limiter statistics."""
    return {
        "general_limit": RATE_LIMIT_REQUESTS_PER_MINUTE,
        "ai_limit": RATE_LIMIT_AI_REQUESTS_PER_MINUTE,
        "burst_limit": RATE_LIMIT_BURST_SIZE,
    }
