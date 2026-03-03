"""Comprehensive endpoint test for Observability + Security architectures."""
import urllib.request
import time
import sys

endpoints = [
    # === OBSERVABILITY (20 key endpoints) ===
    "/api/observability/dashboard",
    "/api/observability/dashboard/system",
    "/api/observability/dashboard/ai",
    "/api/observability/dashboard/users",
    "/api/observability/dashboard/business",
    "/api/observability/logs/stats",
    "/api/observability/logs/recent",
    "/api/observability/logs/errors",
    "/api/observability/traces/stats",
    "/api/observability/traces/recent",
    "/api/observability/ai/stats",
    "/api/observability/ai/models",
    "/api/observability/ai/drift",
    "/api/observability/alerts/stats",
    "/api/observability/alerts/rules",
    "/api/observability/alerts/active",
    "/api/observability/cost/stats",
    "/api/observability/cost/daily",
    "/api/observability/journeys/stats",
    "/api/observability/failures/stats",
    "/api/observability/architecture",
    # === SECURITY (25 key endpoints) ===
    "/api/security/overview",
    "/api/security/architecture",
    "/api/security/tokens/stats",
    "/api/security/tokens/sessions",
    "/api/security/rbac/stats",
    "/api/security/rbac/matrix",
    "/api/security/rbac/permissions",
    "/api/security/encryption/stats",
    "/api/security/encryption/classifications",
    "/api/security/encryption/operations",
    "/api/security/ai/stats",
    "/api/security/ai/threats",
    "/api/security/threats/stats",
    "/api/security/threats/active",
    "/api/security/threats/blocks",
    "/api/security/compliance/stats",
    "/api/security/compliance/retention",
    "/api/security/compliance/retention/check",
    "/api/security/compliance/consent/history",
    "/api/security/compliance/dsr/pending",
    "/api/security/compliance/dsr/history",
    "/api/security/incidents/stats",
    "/api/security/incidents/active",
    "/api/security/incidents/resolved",
    "/api/security/incidents/playbooks",
    "/api/security/audit/stats",
    "/api/security/audit/recent",
    "/api/security/audit/failures",
    "/api/security/audit/integrity",
    # === EXISTING (sanity check) ===
    "/health",
    "/api/data/overview",
    "/api/performance/overview",
]

ok = err = 0
for ep in endpoints:
    try:
        r = urllib.request.urlopen(f"http://127.0.0.1:8000{ep}", timeout=20)
        data = r.read()
        r.close()
        ok += 1
        sys.stdout.write(f"  OK   {ep}\n")
        sys.stdout.flush()
    except Exception as e:
        err += 1
        msg = str(e)[:80]
        sys.stdout.write(f"  FAIL {ep} -> {msg}\n")
        sys.stdout.flush()
    time.sleep(0.6)

sys.stdout.write(f"\n{'='*60}\n")
sys.stdout.write(f"Results: {ok} OK, {err} ERRORS out of {len(endpoints)} endpoints\n")
sys.stdout.flush()
