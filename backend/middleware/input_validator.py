"""
Input Validator & Sanitizer Middleware — API Gateway Security Layer
═══════════════════════════════════════════════════════════════════
Prevents: Prompt injection, XSS, oversized payloads, malicious inputs.

Architecture: "Sanitization firewall before AI layer"
"""
import re
import json
import html
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# ── Maximum allowed payload sizes ──
MAX_BODY_SIZE = 1_048_576  # 1 MB general
MAX_TEXT_FIELD_LENGTH = 10_000  # 10K chars per text field
MAX_AI_PROMPT_LENGTH = 5_000  # 5K chars for user-facing AI inputs

# ── Prompt Injection Patterns ──
# These detect attempts to manipulate AI behavior through user inputs.
PROMPT_INJECTION_PATTERNS = [
    # Direct instruction override
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"ignore\s+(all\s+)?above\s+instructions",
    r"disregard\s+(all\s+)?(previous|above|prior)",
    r"forget\s+(all\s+)?(previous|above|prior)\s+(instructions|context|rules)",
    # System prompt extraction
    r"(what|show|reveal|repeat|display)\s+(is|are)?\s*(your|the|my)\s*(system\s+)?(prompt|instructions|rules|directives)",
    r"output\s+(your|the)\s+(system\s+)?(prompt|instructions)",
    # Role hijacking
    r"you\s+are\s+now\s+(a|an|the)",
    r"act\s+as\s+(a|an|the)\s+(?!survey|interviewer|researcher)",
    r"pretend\s+(you\s+are|to\s+be)\s+(a|an|the)",
    r"switch\s+to\s+.{0,20}\s+mode",
    r"enter\s+.{0,20}\s+mode",
    # Data exfiltration
    r"(output|print|show|reveal|display)\s+(all|every|the)\s+(data|responses|answers|database|users|passwords|keys|tokens|secrets)",
    r"(what|show)\s+(are|is)\s+(the\s+)?(api|secret|private)\s*(key|token|password)",
    # Delimiter injection
    r"```\s*system",
    r"\[SYSTEM\]",
    r"\[INST\]",
    r"<\|im_start\|>",
    r"<\|system\|>",
    r"###\s*(SYSTEM|INSTRUCTION|HUMAN|ASSISTANT)",
]

# Compile patterns for performance
_injection_patterns = [re.compile(p, re.IGNORECASE) for p in PROMPT_INJECTION_PATTERNS]

# ── XSS / HTML Injection patterns ──
XSS_PATTERNS = [
    r"<script\b",
    r"javascript\s*:",
    r"on\w+\s*=\s*[\"']",
    r"<iframe\b",
    r"<object\b",
    r"<embed\b",
    r"<form\b.*action\s*=",
    r"eval\s*\(",
    r"document\.(cookie|domain|write)",
]
_xss_patterns = [re.compile(p, re.IGNORECASE) for p in XSS_PATTERNS]


def sanitize_text(text: str) -> str:
    """
    Sanitize a text string:
    1. HTML-escape dangerous characters
    2. Strip null bytes
    3. Normalize whitespace
    4. Truncate to max length
    """
    if not isinstance(text, str):
        return text

    # Strip null bytes
    text = text.replace("\x00", "")

    # Normalize excessive whitespace (but preserve intentional newlines)
    text = re.sub(r"[ \t]{10,}", "  ", text)  # Collapse excessive spaces
    text = re.sub(r"\n{5,}", "\n\n\n", text)  # Collapse excessive newlines

    # Truncate
    if len(text) > MAX_TEXT_FIELD_LENGTH:
        text = text[:MAX_TEXT_FIELD_LENGTH] + "... [truncated]"

    return text


def check_prompt_injection(text: str) -> tuple:
    """
    Check text for prompt injection attempts.
    Returns (is_safe: bool, matched_pattern: str | None)
    """
    if not isinstance(text, str):
        return True, None

    for pattern in _injection_patterns:
        match = pattern.search(text)
        if match:
            return False, match.group(0)

    return True, None


def check_xss(text: str) -> tuple:
    """
    Check text for XSS/HTML injection attempts.
    Returns (is_safe: bool, matched_pattern: str | None)
    """
    if not isinstance(text, str):
        return True, None

    for pattern in _xss_patterns:
        match = pattern.search(text)
        if match:
            return False, match.group(0)

    return True, None


def _deep_sanitize(obj, path="root"):
    """
    Recursively sanitize all string values in a dict/list.
    Returns (sanitized_obj, injection_found: bool, detail: str)
    """
    if isinstance(obj, str):
        # Check for prompt injection
        safe, matched = check_prompt_injection(obj)
        if not safe:
            return None, True, f"Prompt injection detected at {path}: '{matched}'"

        # Check for XSS
        safe, matched = check_xss(obj)
        if not safe:
            # Don't block, just sanitize
            obj = html.escape(obj)

        return sanitize_text(obj), False, ""

    elif isinstance(obj, dict):
        result = {}
        for key, value in obj.items():
            sanitized, blocked, detail = _deep_sanitize(value, f"{path}.{key}")
            if blocked:
                return None, True, detail
            result[key] = sanitized
        return result, False, ""

    elif isinstance(obj, list):
        result = []
        for i, item in enumerate(obj):
            sanitized, blocked, detail = _deep_sanitize(item, f"{path}[{i}]")
            if blocked:
                return None, True, detail
            result.append(sanitized)
        return result, False, ""

    else:
        return obj, False, ""


# ── Paths that should skip sanitization (e.g., file uploads) ──
SKIP_SANITIZATION_PATHS = {
    "/api/transcribe",  # Audio file upload
}

# ── Paths with AI input that need strict prompt injection checking ──
AI_INPUT_PATHS = {
    "/api/surveys/intake/clarify",
    "/api/surveys/goals/ai-parse",
    "/api/interviews/chat",
    "/api/interviews/respond",
}


class InputValidatorMiddleware(BaseHTTPMiddleware):
    """
    Middleware that validates and sanitizes all incoming request bodies.

    1. Checks payload size via Content-Length header
    2. Body-level deep sanitization is deferred to route handlers
       (reading the body inside BaseHTTPMiddleware causes stream-consumption
       deadlocks in Starlette, so we only inspect headers here).

    Use validate_survey_text() or validate_ai_input() inside route handlers
    for prompt-injection and XSS checks on specific fields.
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        method = request.method

        # Skip for GET/HEAD/OPTIONS requests (no body)
        if method in ("GET", "HEAD", "OPTIONS"):
            return await call_next(request)

        # Skip for specific paths (file uploads etc.)
        if path in SKIP_SANITIZATION_PATHS:
            return await call_next(request)

        # ── Check content length (header-only, no body read) ──
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
                if size > MAX_BODY_SIZE:
                    return JSONResponse(
                        status_code=413,
                        content={"detail": f"Request body too large. Max {MAX_BODY_SIZE} bytes."}
                    )
            except ValueError:
                pass

        # NOTE: We intentionally do NOT read request.body() here.
        # BaseHTTPMiddleware consumes the receive stream, causing call_next()
        # to hang when FastAPI tries to re-read the body for Pydantic parsing.
        # Input validation (prompt injection, XSS) should be done at the
        # route handler level using validate_survey_text / validate_ai_input.

        return await call_next(request)


def validate_survey_text(text: str) -> tuple:
    """
    Validate a survey-related text input (question text, description, etc.).
    Returns (is_valid: bool, cleaned_text: str, error: str | None)
    """
    if not text or not text.strip():
        return False, "", "Text cannot be empty"

    if len(text) > MAX_TEXT_FIELD_LENGTH:
        return False, "", f"Text exceeds maximum length of {MAX_TEXT_FIELD_LENGTH} characters"

    safe, matched = check_prompt_injection(text)
    if not safe:
        return False, "", "Input contains disallowed content"

    cleaned = sanitize_text(text)
    return True, cleaned, None


def validate_ai_input(text: str) -> tuple:
    """
    Stricter validation for text going directly to AI models.
    Returns (is_valid: bool, cleaned_text: str, error: str | None)
    """
    if not text or not text.strip():
        return False, "", "Input cannot be empty"

    if len(text) > MAX_AI_PROMPT_LENGTH:
        return False, "", f"Input exceeds maximum length of {MAX_AI_PROMPT_LENGTH} characters"

    safe, matched = check_prompt_injection(text)
    if not safe:
        return False, "", "Input contains disallowed content"

    safe, matched = check_xss(text)
    if not safe:
        text = html.escape(text)

    cleaned = sanitize_text(text)
    return True, cleaned, None
