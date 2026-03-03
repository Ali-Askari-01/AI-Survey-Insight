"""
JWT Authentication Middleware & Utilities
Handles token creation, verification, password hashing, and role-based access.
"""
import hashlib
import hmac
import json
import os
import time
import base64
import re
from datetime import datetime, timedelta
from fastapi import HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .config import JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRATION_HOURS

security = HTTPBearer(auto_error=False)


# ── Password Hashing (PBKDF2-SHA256 with per-user random salt) ──
# OWASP 2023: min 600,000 iterations for PBKDF2-SHA256
_PBKDF2_ITERATIONS = 600_000


def hash_password(password: str) -> str:
    """Hash a password using PBKDF2-SHA256 with a random 16-byte salt.
    Returns format: salt_hex:hash_hex (per-user unique salt)."""
    salt = os.urandom(16)
    pw_hash = hashlib.pbkdf2_hmac(
        'sha256', password.encode(), salt, _PBKDF2_ITERATIONS
    )
    return f"{salt.hex()}:{pw_hash.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a password against its stored hash.
    Supports both new (salt:hash) and legacy (hash-only) formats."""
    if ':' in stored_hash:
        # New format: salt_hex:hash_hex
        salt_hex, hash_hex = stored_hash.split(':', 1)
        salt = bytes.fromhex(salt_hex)
        computed = hashlib.pbkdf2_hmac(
            'sha256', password.encode(), salt, _PBKDF2_ITERATIONS
        )
        return hmac.compare_digest(computed, bytes.fromhex(hash_hex))
    else:
        # Legacy format: static salt from JWT_SECRET (backward compat)
        legacy_salt = hashlib.sha256(JWT_SECRET.encode()).hexdigest()[:16]
        legacy_hash = hashlib.pbkdf2_hmac(
            'sha256', password.encode(), legacy_salt.encode(), 100000
        ).hex()
        return hmac.compare_digest(legacy_hash, stored_hash)


# ── JWT Token Management (pure Python — no PyJWT dependency) ──
def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()


def _b64decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    if padding != 4:
        s += '=' * padding
    return base64.urlsafe_b64decode(s)


def create_token(user_id: int, email: str, role: str) -> str:
    """Create a JWT access token."""
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "exp": int(time.time()) + (JWT_EXPIRATION_HOURS * 3600),
        "iat": int(time.time()),
    }
    header_b64 = _b64encode(json.dumps(header).encode())
    payload_b64 = _b64encode(json.dumps(payload).encode())
    signing_input = f"{header_b64}.{payload_b64}"
    signature = hmac.new(
        JWT_SECRET.encode(), signing_input.encode(), hashlib.sha256
    ).digest()
    sig_b64 = _b64encode(signature)
    return f"{header_b64}.{payload_b64}.{sig_b64}"


def decode_token(token: str) -> dict:
    """Decode and verify a JWT token. Raises HTTPException on failure."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Invalid token format")

        header_b64, payload_b64, sig_b64 = parts
        # Verify signature
        signing_input = f"{header_b64}.{payload_b64}"
        expected_sig = hmac.new(
            JWT_SECRET.encode(), signing_input.encode(), hashlib.sha256
        ).digest()
        actual_sig = _b64decode(sig_b64)
        if not hmac.compare_digest(expected_sig, actual_sig):
            raise ValueError("Invalid signature")

        # Decode payload
        payload = json.loads(_b64decode(payload_b64))

        # Check expiration
        if payload.get("exp", 0) < time.time():
            raise ValueError("Token expired")

        return payload
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")


# ── Password Validation ──
def validate_password_strength(password: str) -> str | None:
    """Validate password meets complexity requirements.
    Returns error message string if invalid, None if valid."""
    if len(password) < 8:
        return "Password must be at least 8 characters long"
    if not re.search(r'[A-Z]', password):
        return "Password must contain at least one uppercase letter"
    if not re.search(r'[a-z]', password):
        return "Password must contain at least one lowercase letter"
    if not re.search(r'[0-9]', password):
        return "Password must contain at least one number"
    return None


# ── FastAPI Dependencies ──
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Dependency: extract and verify user from Bearer token."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    return decode_token(credentials.credentials)


async def get_optional_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Dependency: optionally extract user (returns None if no token)."""
    if not credentials:
        return None
    try:
        return decode_token(credentials.credentials)
    except HTTPException:
        return None


def require_role(*roles):
    """Dependency factory: require specific role(s)."""
    async def role_checker(user: dict = Depends(get_current_user)):
        if user.get("role") not in roles:
            raise HTTPException(
                status_code=403,
                detail=f"Access denied. Required role: {', '.join(roles)}"
            )
        return user
    return role_checker
