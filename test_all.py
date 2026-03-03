import urllib.request, json, time, sys

BASE = "http://127.0.0.1:8000"
passed = 0
failed = 0
errors = []

def t(path, method="GET", body=None):
    global passed, failed
    url = BASE + path
    try:
        if body:
            data = json.dumps(body).encode()
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method=method)
        else:
            req = urllib.request.Request(url, method=method)
        r = urllib.request.urlopen(req, timeout=8)
        passed += 1
        print(f"  OK  {path}")
    except Exception as e:
        failed += 1
        msg = str(e)[:100]
        errors.append(f"{path} => {msg}")
        print(f"  FAIL {path} => {msg}")

print("=" * 60)
print("OBSERVABILITY ENDPOINTS")
print("=" * 60)

# Dashboard panels
for p in ["system", "ai", "users", "business", "cost", "alerts", "failures"]:
    t(f"/api/observability/dashboard/{p}")
    time.sleep(0.4)

# Logs
for p in ["stats", "recent", "errors", "search?keyword=test", "rate"]:
    t(f"/api/observability/logs/{p}")
    time.sleep(0.4)

# Traces
for p in ["stats", "recent", "slow", "span-analytics", "bottlenecks"]:
    t(f"/api/observability/traces/{p}")
    time.sleep(0.4)

# AI
for p in ["stats", "models", "tasks", "drift", "prompts", "failures", "recent-calls"]:
    t(f"/api/observability/ai/{p}")
    time.sleep(0.4)

# Alerts
for p in ["stats", "rules", "active", "history"]:
    t(f"/api/observability/alerts/{p}")
    time.sleep(0.4)

# Cost
for p in ["stats", "daily", "models", "channels", "per-interview", "budget"]:
    t(f"/api/observability/cost/{p}")
    time.sleep(0.4)

# Journeys
for p in ["stats", "funnel", "active"]:
    t(f"/api/observability/journeys/{p}")
    time.sleep(0.4)

# Failures
for p in ["stats", "recent", "patterns", "spike", "recommendations", "correlations"]:
    t(f"/api/observability/failures/{p}")
    time.sleep(0.4)

# Architecture + aggregate dashboard
t("/api/observability/architecture")
time.sleep(0.4)
t("/api/observability/dashboard")
time.sleep(0.4)

obs_p, obs_f = passed, failed
print(f"\nObservability: {obs_p} passed, {obs_f} failed")

print("\n" + "=" * 60)
print("SECURITY ENDPOINTS")
print("=" * 60)
passed, failed = 0, 0

# Overview
t("/api/security/overview")
time.sleep(0.4)
t("/api/security/architecture")
time.sleep(0.4)

# Tokens
for p in ["stats", "sessions"]:
    t(f"/api/security/tokens/{p}")
    time.sleep(0.4)

# RBAC
for p in ["stats", "matrix", "permissions", "user/1", "audit"]:
    t(f"/api/security/rbac/{p}")
    time.sleep(0.4)

# Encryption
for p in ["stats", "classifications", "operations"]:
    t(f"/api/security/encryption/{p}")
    time.sleep(0.4)

# AI Security
for p in ["stats", "threats"]:
    t(f"/api/security/ai/{p}")
    time.sleep(0.4)

# Threats
for p in ["stats", "active", "blocks"]:
    t(f"/api/security/threats/{p}")
    time.sleep(0.4)

# Compliance
t("/api/security/compliance/stats")
time.sleep(0.4)
t("/api/security/compliance/retention")
time.sleep(0.4)
t("/api/security/compliance/consent/user1")
time.sleep(0.4)
t("/api/security/compliance/dsr/pending")
time.sleep(0.4)
t("/api/security/compliance/dsr/history")
time.sleep(0.4)

# Incidents
for p in ["stats", "active", "resolved", "playbooks"]:
    t(f"/api/security/incidents/{p}")
    time.sleep(0.4)

# Audit
for p in ["stats", "recent", "by-category/authentication", "by-user/admin", "failures", "integrity", "search?keyword=test"]:
    t(f"/api/security/audit/{p}")
    time.sleep(0.4)

# POST endpoints
t("/api/security/rbac/check", "POST", {"user_id": "admin", "permission": "read", "resource": "surveys"})
time.sleep(0.4)
t("/api/security/encryption/encrypt", "POST", {"data": {"name": "test"}, "classification": "internal"})
time.sleep(0.4)
t("/api/security/encryption/decrypt", "POST", {"data": {"name": "encrypted"}, "classification": "internal"})
time.sleep(0.4)
t("/api/security/ai/scan-prompt", "POST", {"prompt": "Analyze this feedback", "context": "test"})
time.sleep(0.4)
t("/api/security/ai/scan-output", "POST", {"output": "Results show positive trends", "task_type": "analysis"})
time.sleep(0.4)
t("/api/security/ai/validate-request", "POST", {"model": "gemini-2.5-flash", "prompt": "test", "task_type": "analysis"})
time.sleep(0.4)
t("/api/security/ai/validate-response", "POST", {"output": "test output", "task_type": "analysis", "model": "gemini-2.5-flash"})
time.sleep(0.4)
t("/api/security/ai/check-budget", "POST", {"model": "gemini-2.5-flash", "estimated_tokens": 1000})
time.sleep(0.4)
t("/api/security/threats/record-request", "POST", {"ip": "192.168.1.1", "endpoint": "/api/test", "user_id": "user1"})
time.sleep(0.4)
t("/api/security/threats/check-session", "POST", {"session_id": "sess_123", "ip": "192.168.1.1", "user_id": "user1"})
time.sleep(0.4)
t("/api/security/threats/ip-reputation", "POST", {"ip": "192.168.1.1"})
time.sleep(0.4)
t("/api/security/compliance/consent", "POST", {"user_id": "user1", "consent_type": "data_collection", "granted": True})
time.sleep(0.4)
t("/api/security/compliance/dsr", "POST", {"user_id": "user1", "request_type": "access", "details": "My data"})
time.sleep(0.4)
t("/api/security/incidents/create", "POST", {"title": "Test Incident", "severity": "low", "description": "Test"})
time.sleep(0.4)

sec_p, sec_f = passed, failed
print(f"\nSecurity: {sec_p} passed, {sec_f} failed")

print("\n" + "=" * 60)
total_p = obs_p + sec_p
total_f = obs_f + sec_f
print(f"GRAND TOTAL: {total_p} passed, {total_f} failed out of {total_p + total_f}")
if errors:
    print(f"\nFailed:")
    for e in errors:
        print(f"  {e}")
print("=" * 60)
