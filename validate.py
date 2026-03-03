"""Quick validation of all Observability + Security endpoints."""
import urllib.request
import json
import time
import sys

BASE = "http://127.0.0.1:8000"
passed = 0
failed = 0
errors = []

def test(method, path, body=None, expect=200):
    global passed, failed
    url = BASE + path
    try:
        if body is not None:
            data = json.dumps(body).encode()
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method=method)
        else:
            req = urllib.request.Request(url, method=method)
        r = urllib.request.urlopen(req, timeout=10)
        code = r.status
        if code == expect:
            passed += 1
            sys.stdout.write(".")
        else:
            failed += 1
            errors.append(f"{method} {path} => {code} (expected {expect})")
            sys.stdout.write("F")
    except Exception as e:
        failed += 1
        errors.append(f"{method} {path} => {e}")
        sys.stdout.write("F")
    sys.stdout.flush()
    time.sleep(0.3)

print("=== OBSERVABILITY ENDPOINTS ===")

# Dashboard panels (skip aggregate /dashboard to avoid slow DB on first hit)
test("GET", "/api/observability/dashboard/system")
test("GET", "/api/observability/dashboard/ai")
test("GET", "/api/observability/dashboard/users")
test("GET", "/api/observability/dashboard/business")
test("GET", "/api/observability/dashboard/cost")
test("GET", "/api/observability/dashboard/alerts")
test("GET", "/api/observability/dashboard/failures")

# Logs
test("GET", "/api/observability/logs/stats")
test("GET", "/api/observability/logs/recent")
test("GET", "/api/observability/logs/errors")
test("GET", "/api/observability/logs/search?keyword=test")
test("GET", "/api/observability/logs/rate")

# Traces
test("GET", "/api/observability/traces/stats")
test("GET", "/api/observability/traces/recent")
test("GET", "/api/observability/traces/slow")
test("GET", "/api/observability/traces/span-analytics")
test("GET", "/api/observability/traces/bottlenecks")

# AI Observability
test("GET", "/api/observability/ai/stats")
test("GET", "/api/observability/ai/models")
test("GET", "/api/observability/ai/tasks")
test("GET", "/api/observability/ai/drift")
test("GET", "/api/observability/ai/prompts")
test("GET", "/api/observability/ai/failures")
test("GET", "/api/observability/ai/recent-calls")

# Alerts
test("GET", "/api/observability/alerts/stats")
test("GET", "/api/observability/alerts/rules")
test("GET", "/api/observability/alerts/active")
test("GET", "/api/observability/alerts/history")

# Cost
test("GET", "/api/observability/cost/stats")
test("GET", "/api/observability/cost/daily")
test("GET", "/api/observability/cost/models")
test("GET", "/api/observability/cost/channels")
test("GET", "/api/observability/cost/per-interview")
test("GET", "/api/observability/cost/budget")

# User Journeys
test("GET", "/api/observability/journeys/stats")
test("GET", "/api/observability/journeys/funnel")
test("GET", "/api/observability/journeys/active")

# Failures
test("GET", "/api/observability/failures/stats")
test("GET", "/api/observability/failures/recent")
test("GET", "/api/observability/failures/patterns")
test("GET", "/api/observability/failures/spike")
test("GET", "/api/observability/failures/recommendations")
test("GET", "/api/observability/failures/correlations")

# Architecture
test("GET", "/api/observability/architecture")

# Now test the aggregate dashboard (last, because it's slower)
test("GET", "/api/observability/dashboard")

print(f"\nObservability: {passed} passed, {failed} failed")
obs_passed = passed
obs_failed = failed

# Reset for security
passed = 0
failed = 0

print("\n=== SECURITY ENDPOINTS ===")

# Overview & Architecture
test("GET", "/api/security/overview")
test("GET", "/api/security/architecture")

# Tokens
test("GET", "/api/security/tokens/stats")
test("GET", "/api/security/tokens/sessions")

# RBAC
test("GET", "/api/security/rbac/stats")
test("GET", "/api/security/rbac/matrix")
test("GET", "/api/security/rbac/permissions")
test("GET", "/api/security/rbac/user/1")
test("GET", "/api/security/rbac/audit")

# Encryption
test("GET", "/api/security/encryption/stats")
test("GET", "/api/security/encryption/classifications")
test("GET", "/api/security/encryption/operations")

# AI Security
test("GET", "/api/security/ai/stats")
test("GET", "/api/security/ai/threats")

# Threats
test("GET", "/api/security/threats/stats")
test("GET", "/api/security/threats/active")
test("GET", "/api/security/threats/blocks")

# Compliance
test("GET", "/api/security/compliance/stats")
test("GET", "/api/security/compliance/retention")
test("GET", "/api/security/compliance/consent/user1")
test("GET", "/api/security/compliance/dsr/pending")
test("GET", "/api/security/compliance/dsr/history")

# Incidents
test("GET", "/api/security/incidents/stats")
test("GET", "/api/security/incidents/active")
test("GET", "/api/security/incidents/resolved")
test("GET", "/api/security/incidents/playbooks")

# Audit
test("GET", "/api/security/audit/stats")
test("GET", "/api/security/audit/recent")
test("GET", "/api/security/audit/by-category/authentication")
test("GET", "/api/security/audit/by-user/admin")
test("GET", "/api/security/audit/failures")
test("GET", "/api/security/audit/integrity")
test("GET", "/api/security/audit/search?keyword=test")

# POST endpoints
test("POST", "/api/security/rbac/check", {"user_id": "admin", "permission": "read", "resource": "surveys"})
test("POST", "/api/security/encryption/encrypt", {"data": {"test_field": "test_value"}, "classification": "internal"})
test("POST", "/api/security/encryption/decrypt", {"data": {"test_field": "gAAAA_test"}, "classification": "internal"})
test("POST", "/api/security/ai/scan-prompt", {"prompt": "Analyze this survey feedback", "context": "test"})
test("POST", "/api/security/ai/scan-output", {"output": "The survey results show positive trends", "task_type": "analysis"})
test("POST", "/api/security/ai/validate-request", {"model": "gemini-2.5-flash", "prompt": "test prompt", "task_type": "analysis"})
test("POST", "/api/security/ai/validate-response", {"output": "test output", "task_type": "analysis", "model": "gemini-2.5-flash"})
test("POST", "/api/security/ai/check-budget", {"model": "gemini-2.5-flash", "estimated_tokens": 1000})
test("POST", "/api/security/threats/record-request", {"ip": "192.168.1.1", "endpoint": "/api/test", "user_id": "user1"})
test("POST", "/api/security/threats/check-session", {"session_id": "sess_123", "ip": "192.168.1.1", "user_id": "user1"})
test("POST", "/api/security/threats/ip-reputation", {"ip": "192.168.1.1"})
test("POST", "/api/security/compliance/consent", {"user_id": "user1", "consent_type": "data_collection", "granted": True})
test("POST", "/api/security/compliance/dsr", {"user_id": "user1", "request_type": "access", "details": "Request my data"})
test("POST", "/api/security/incidents/create", {"title": "Test Incident", "severity": "low", "description": "Test"})

print(f"\nSecurity: {passed} passed, {failed} failed")

total_passed = obs_passed + passed
total_failed = obs_failed + failed

print(f"\n{'='*50}")
print(f"TOTAL: {total_passed} passed, {total_failed} failed out of {total_passed + total_failed}")
if errors:
    print(f"\nFailed endpoints:")
    for e in errors:
        print(f"  {e}")
print(f"{'='*50}")
