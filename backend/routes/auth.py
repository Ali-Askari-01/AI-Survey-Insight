"""
Authentication API Routes
Handles user registration, login, profile, Google OAuth, and role management.
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import RedirectResponse
from ..database import get_db
from ..models import UserRegister, UserLogin
from ..auth import hash_password, verify_password, create_token, get_current_user, require_role, validate_password_strength
from ..config import MAX_FAILED_LOGIN_ATTEMPTS, FAILED_LOGIN_LOCKOUT_MINUTES, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI
from datetime import datetime
import re
import time
import threading
import logging
import urllib.parse
import json

router = APIRouter(prefix="/api/auth", tags=["auth"])
security_logger = logging.getLogger("security")

# ── Failed Login Tracker (in-memory, per email) ──
_failed_logins: dict = {}  # email -> {"count": int, "first_failure": float, "locked_until": float}
_failed_lock = threading.Lock()


def _check_login_lockout(email: str) -> str | None:
    """Check if an email is locked out. Returns error message or None."""
    with _failed_lock:
        record = _failed_logins.get(email)
        if not record:
            return None
        now = time.time()
        if record.get("locked_until", 0) > now:
            remaining = int(record["locked_until"] - now)
            mins = remaining // 60 + 1
            return f"Account temporarily locked due to too many failed attempts. Try again in {mins} minute(s)."
        # If lockout expired, reset
        if record.get("locked_until", 0) <= now and record.get("locked_until", 0) > 0:
            del _failed_logins[email]
        return None


def _record_failed_login(email: str):
    """Record a failed login attempt. Lock account after MAX_FAILED_LOGIN_ATTEMPTS."""
    with _failed_lock:
        now = time.time()
        record = _failed_logins.get(email, {"count": 0, "first_failure": now, "locked_until": 0})
        # Reset counter if first failure was more than lockout window ago
        if now - record["first_failure"] > FAILED_LOGIN_LOCKOUT_MINUTES * 60:
            record = {"count": 0, "first_failure": now, "locked_until": 0}
        record["count"] += 1
        if record["count"] >= MAX_FAILED_LOGIN_ATTEMPTS:
            record["locked_until"] = now + (FAILED_LOGIN_LOCKOUT_MINUTES * 60)
        _failed_logins[email] = record


def _clear_failed_logins(email: str):
    """Clear failed login counter on successful login."""
    with _failed_lock:
        _failed_logins.pop(email, None)


@router.post("/register")
def register(user: UserRegister):
    """Register a new user account."""
    # Validate email format
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', user.email):
        raise HTTPException(status_code=400, detail="Invalid email format")

    # Validate password strength
    pw_error = validate_password_strength(user.password)
    if pw_error:
        raise HTTPException(status_code=400, detail=pw_error)

    conn = get_db()
    # Check if email already exists
    existing = conn.execute("SELECT id FROM users WHERE email = ?", (user.email,)).fetchone()
    if existing:
        conn.close()
        raise HTTPException(status_code=409, detail="Email already registered")

    password_hash = hash_password(user.password)
    # Force role to 'pm' — prevent role escalation attacks
    safe_role = "pm"
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users (name, email, password_hash, role)
        VALUES (?, ?, ?, ?)
    """, (user.name, user.email, password_hash, safe_role))
    conn.commit()
    user_id = cursor.lastrowid

    token = create_token(user_id, user.email, safe_role)
    conn.close()

    security_logger.info(f"REGISTER user_id={user_id} email={user.email} role={safe_role}")

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user_id,
            "name": user.name,
            "email": user.email,
            "role": safe_role,
        }
    }


@router.post("/login")
def login(credentials: UserLogin):
    """Log in with email and password."""
    # Check if account is locked out
    lockout_msg = _check_login_lockout(credentials.email)
    if lockout_msg:
        security_logger.warning(f"LOCKOUT email={credentials.email}")
        raise HTTPException(status_code=429, detail=lockout_msg)

    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE email = ?", (credentials.email,)).fetchone()
    if not user:
        conn.close()
        _record_failed_login(credentials.email)
        security_logger.warning(f"LOGIN_FAILED email={credentials.email} reason=not_found")
        raise HTTPException(status_code=401, detail="Invalid email or password")

    user_dict = dict(user)
    if not verify_password(credentials.password, user_dict["password_hash"]):
        conn.close()
        _record_failed_login(credentials.email)
        security_logger.warning(f"LOGIN_FAILED email={credentials.email} reason=bad_password")
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user_dict["is_active"]:
        conn.close()
        raise HTTPException(status_code=403, detail="Account is deactivated")

    # Successful login — clear failed attempts
    _clear_failed_logins(credentials.email)

    # Update last login
    conn.execute("UPDATE users SET last_login = ? WHERE id = ?", (datetime.now().isoformat(), user_dict["id"]))
    conn.commit()

    token = create_token(user_dict["id"], user_dict["email"], user_dict["role"])
    conn.close()

    security_logger.info(f"LOGIN user_id={user_dict['id']} email={user_dict['email']}")

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user_dict["id"],
            "name": user_dict["name"],
            "email": user_dict["email"],
            "role": user_dict["role"],
        }
    }


@router.get("/me")
def get_profile(user: dict = Depends(get_current_user)):
    """Get current user profile."""
    conn = get_db()
    db_user = conn.execute("SELECT * FROM users WHERE id = ?", (user["sub"],)).fetchone()
    conn.close()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    u = dict(db_user)
    return {
        "id": u["id"],
        "name": u["name"],
        "email": u["email"],
        "role": u["role"],
        "is_active": bool(u["is_active"]),
        "last_login": u["last_login"],
        "created_at": u["created_at"],
    }


@router.get("/users")
def list_users(user: dict = Depends(require_role("founder", "pm"))):
    """List all users (founder/PM only)."""
    conn = get_db()
    users = conn.execute("SELECT id, name, email, role, is_active, last_login, created_at FROM users ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(u) for u in users]


@router.put("/users/{user_id}/role")
def update_user_role(user_id: int, data: dict, current_user: dict = Depends(require_role("founder"))):
    """Update a user's role (founder only)."""
    new_role = data.get("role")
    valid_roles = ["founder", "pm", "designer", "engineer", "respondent"]
    if new_role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {', '.join(valid_roles)}")

    conn = get_db()
    conn.execute("UPDATE users SET role = ?, updated_at = ? WHERE id = ?", (new_role, datetime.now().isoformat(), user_id))
    conn.commit()
    conn.close()
    return {"message": f"User role updated to {new_role}"}


@router.put("/users/{user_id}/deactivate")
def deactivate_user(user_id: int, current_user: dict = Depends(require_role("founder"))):
    """Deactivate a user account (founder only)."""
    conn = get_db()
    conn.execute("UPDATE users SET is_active = 0, updated_at = ? WHERE id = ?", (datetime.now().isoformat(), user_id))
    conn.commit()
    conn.close()
    return {"message": "User deactivated"}


# ═══════════════════════════════════════════════════
# GOOGLE OAUTH 2.0 — Sign in with Google
# ═══════════════════════════════════════════════════

@router.get("/google/login")
def google_login(request: Request):
    """Redirect user to Google's OAuth2 consent screen."""
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=501, detail="Google Sign-In is not configured")

    # Build redirect URI dynamically from current request host
    scheme = request.headers.get("x-forwarded-proto", "http")
    host = request.headers.get("host", "localhost:8000")
    redirect_uri = f"{scheme}://{host}/api/auth/google/callback"

    params = urllib.parse.urlencode({
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
        "state": redirect_uri,  # pass redirect_uri in state for callback
    })
    return RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{params}")


@router.get("/google/callback")
def google_callback(request: Request, code: str = None, error: str = None, state: str = None):
    """Handle the OAuth2 callback from Google."""
    if error:
        return RedirectResponse(f"/app?auth_error={urllib.parse.quote(error)}")

    if not code:
        return RedirectResponse("/app?auth_error=no_code")

    # Use the redirect_uri from state parameter, or build from request
    if state:
        redirect_uri = state
    else:
        scheme = request.headers.get("x-forwarded-proto", "http")
        host = request.headers.get("host", "localhost:8000")
        redirect_uri = f"{scheme}://{host}/api/auth/google/callback"

    # Exchange authorization code for tokens
    import urllib.request
    token_data = urllib.parse.urlencode({
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }).encode()

    try:
        req = urllib.request.Request(
            "https://oauth2.googleapis.com/token",
            data=token_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            token_response = json.loads(resp.read())
    except Exception as e:
        security_logger.error(f"GOOGLE_TOKEN_EXCHANGE_FAILED: {e}")
        return RedirectResponse("/app?auth_error=token_exchange_failed")

    id_token = token_response.get("id_token")
    if not id_token:
        return RedirectResponse("/app?auth_error=no_id_token")

    # Decode the ID token to get user info (Google ID tokens are JWTs)
    try:
        # Decode payload (middle segment) — signature verified by Google's token endpoint
        import base64
        payload_b64 = id_token.split('.')[1]
        # Add padding
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += '=' * padding
        user_info = json.loads(base64.urlsafe_b64decode(payload_b64))
    except Exception as e:
        security_logger.error(f"GOOGLE_ID_TOKEN_DECODE_FAILED: {e}")
        return RedirectResponse("/app?auth_error=invalid_token")

    email = user_info.get("email", "")
    name = user_info.get("name", email.split("@")[0])
    avatar_url = user_info.get("picture", "")

    if not email:
        return RedirectResponse("/app?auth_error=no_email")

    # Find or create user
    conn = get_db()
    existing = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

    if existing:
        user_dict = dict(existing)
        if not user_dict["is_active"]:
            conn.close()
            return RedirectResponse("/app?auth_error=account_deactivated")

        # Update last login and avatar
        conn.execute(
            "UPDATE users SET last_login = ?, avatar_url = ?, updated_at = ? WHERE id = ?",
            (datetime.now().isoformat(), avatar_url, datetime.now().isoformat(), user_dict["id"])
        )
        conn.commit()
        user_id = user_dict["id"]
        role = user_dict["role"]
    else:
        # Auto-register new Google user
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users (name, email, password_hash, role, avatar_url, last_login)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name, email, "google_oauth", "pm", avatar_url, datetime.now().isoformat()))
        conn.commit()
        user_id = cursor.lastrowid
        role = "pm"
        security_logger.info(f"GOOGLE_REGISTER user_id={user_id} email={email}")

    conn.close()

    # Create JWT
    jwt_token = create_token(user_id, email, role)
    security_logger.info(f"GOOGLE_LOGIN user_id={user_id} email={email}")

    # Redirect to frontend with token
    return RedirectResponse(f"/app?google_token={jwt_token}")


@router.get("/google/client-id")
def google_client_id():
    """Return the Google Client ID for the frontend to display the button."""
    return {"client_id": GOOGLE_CLIENT_ID if GOOGLE_CLIENT_ID else None}
