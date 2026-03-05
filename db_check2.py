import sqlite3
conn = sqlite3.connect('data/survey_engine.db')
conn.row_factory = sqlite3.Row

print("=== RESPONSES SCHEMA ===")
for col in conn.execute("PRAGMA table_info(responses)").fetchall():
    d = dict(col)
    print(f"  {d['name']} ({d['type']})")

print("\n=== RECENT RESPONSES ===")
rows = conn.execute("SELECT * FROM responses ORDER BY created_at DESC LIMIT 5").fetchall()
for r in rows:
    d = dict(r)
    print(f"  Keys: {list(d.keys())}")
    for k, v in d.items():
        print(f"    {k} = {str(v)[:80]}")
    print()

print("=== CONVERSATION_HISTORY SCHEMA ===")
for col in conn.execute("PRAGMA table_info(conversation_history)").fetchall():
    d = dict(col)
    print(f"  {d['name']} ({d['type']})")

print("\n=== RECENT CONVERSATION HISTORY (survey 8 - Lack of Sports) ===")
sess8 = conn.execute("SELECT session_id FROM interview_sessions WHERE survey_id IN (7,8) LIMIT 5").fetchall()
for s in sess8:
    sid = dict(s)['session_id']
    print(f"\n  Session: {sid[:30]}")
    history = conn.execute("SELECT role, message FROM conversation_history WHERE session_id=? ORDER BY created_at", (sid,)).fetchall()
    for h in history:
        hd = dict(h)
        print(f"    [{hd['role']}] {str(hd['message'])[:80]}")

print("\n=== ALL SESSIONS FOR SURVEY 7 & 8 ===")
for s in conn.execute("SELECT session_id, survey_id, status, completion_percentage, respondent_id FROM interview_sessions WHERE survey_id IN (7,8)").fetchall():
    sd = dict(s)
    print(f"  sid={sd['session_id'][:25]} survey={sd['survey_id']} status={sd['status']} comp={sd['completion_percentage']}%")

conn.close()
