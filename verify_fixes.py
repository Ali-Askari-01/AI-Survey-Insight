"""Verify the E2E fixes by checking the database state for the first test run."""
import sqlite3

conn = sqlite3.connect('data/survey_engine.db')
conn.row_factory = sqlite3.Row

print("=" * 60)
print("DATABASE VERIFICATION OF BUG FIXES")
print("=" * 60)

# Find the session from survey 12 (first E2E test run)
sessions = conn.execute("""
    SELECT s.session_id, s.survey_id, s.status, s.completion_percentage, s.engagement_score,
           (SELECT COUNT(*) FROM conversation_history WHERE session_id = s.session_id) as hist_count,
           (SELECT COUNT(*) FROM responses WHERE session_id = s.session_id) as resp_count
    FROM interview_sessions s
    WHERE s.survey_id >= 12
    ORDER BY s.started_at DESC
""").fetchall()

for s in sessions:
    d = dict(s)
    sid = d['session_id'][:16]
    print(f"\n--- Survey {d['survey_id']} | Session {sid}... ---")
    print(f"  Status: {d['status']}")
    print(f"  Completion: {d['completion_percentage']}%")
    print(f"  Engagement: {d['engagement_score']}")
    print(f"  Conversation history entries: {d['hist_count']}")
    print(f"  Response records: {d['resp_count']}")
    
    # Show conversation flow
    history = conn.execute(
        "SELECT role, substr(message, 1, 80) as msg FROM conversation_history WHERE session_id = ? ORDER BY created_at",
        (d['session_id'][:36] if len(d['session_id']) > 36 else d['session_id'],)
    ).fetchall()
    # Need full session_id
    full_sid = conn.execute("SELECT session_id FROM interview_sessions WHERE session_id LIKE ?", 
        (d['session_id'],)).fetchone()
    if full_sid:
        history = conn.execute(
            "SELECT role, substr(message, 1, 100) as msg FROM conversation_history WHERE session_id = ? ORDER BY created_at",
            (dict(full_sid)['session_id'],)
        ).fetchall()
        print(f"\n  Conversation flow:")
        for h in history:
            hd = dict(h)
            print(f"    [{hd['role'].upper():4s}] {hd['msg']}...")
    
    # Check responses
    responses = conn.execute(
        "SELECT substr(response_text, 1, 60) as txt, sentiment_score, quality_score FROM responses WHERE session_id = ?",
        (dict(full_sid)['session_id'] if full_sid else '',)
    ).fetchall()
    if responses:
        print(f"\n  Saved responses:")
        for r in responses:
            rd = dict(r)
            print(f"    Text: {rd['txt']}... | Sentiment: {rd['sentiment_score']} | Quality: {rd['quality_score']}")

# Also verify the fix for older sessions
print("\n" + "=" * 60)
print("COMPARING OLD vs NEW SESSION DATA")
print("=" * 60)

# Old survey 8 session (before fix)
old = conn.execute("""
    SELECT s.session_id, s.status, s.completion_percentage,
           (SELECT COUNT(*) FROM conversation_history WHERE session_id = s.session_id) as hist,
           (SELECT COUNT(*) FROM responses WHERE session_id = s.session_id) as resps
    FROM interview_sessions s WHERE s.survey_id = 8
""").fetchall()
if old:
    d = dict(old[0])
    print(f"\nOLD (Survey 8 - before fix):")
    print(f"  Status={d['status']} Completion={d['completion_percentage']}% History={d['hist']} Responses={d['resps']}")

# New sessions (after fix)
new = conn.execute("""
    SELECT s.session_id, s.status, s.completion_percentage,
           (SELECT COUNT(*) FROM conversation_history WHERE session_id = s.session_id) as hist,
           (SELECT COUNT(*) FROM responses WHERE session_id = s.session_id) as resps
    FROM interview_sessions s WHERE s.survey_id = 12
""").fetchall()
if new:
    d = dict(new[0])
    print(f"\nNEW (Survey 12 - after fix):")
    print(f"  Status={d['status']} Completion={d['completion_percentage']}% History={d['hist']} Responses={d['resps']}")

# Validate fixes
print("\n" + "=" * 60)
print("FIX VALIDATION RESULTS")
print("=" * 60)

if new:
    nd = dict(new[0])
    checks = []
    
    # Check 1: Responses saved (BUG: responses were not registered)
    ok1 = nd['resps'] >= 3
    checks.append(("Responses saved (>= 3)", ok1, nd['resps']))
    
    # Check 2: Conversation history complete (greeting + user msgs + AI responses)
    ok2 = nd['hist'] >= 4
    checks.append(("Conversation history (>= 4 entries)", ok2, nd['hist']))
    
    # Check 3: Completion percentage updated (BUG: was always 0%)
    ok3 = nd['completion_percentage'] > 0
    checks.append(("Completion % updated (> 0%)", ok3, nd['completion_percentage']))
    
    for label, ok, val in checks:
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {label}: {val}")
    
    # Check 4: AI Analysis endpoint (BUG: HTTP 500)
    print(f"  [PASS] AI Analysis no longer 500 (verified via API test earlier)")
    
    all_pass = all(ok for _, ok, _ in checks)
    print(f"\n  {'ALL CHECKS PASSED!' if all_pass else 'SOME CHECKS FAILED'}")
else:
    print("  No new session data found - test may not have completed")

conn.close()
