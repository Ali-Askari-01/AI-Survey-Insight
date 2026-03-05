import sqlite3
conn = sqlite3.connect('data/survey_engine.db')
conn.row_factory = sqlite3.Row

print("=== SURVEYS ===")
for r in conn.execute('SELECT id,title,status FROM surveys').fetchall():
    d = dict(r)
    print(f"  ID={d['id']} Title={d['title'][:40]} Status={d['status']}")

print("\n=== SESSIONS ===")
sessions = [dict(r) for r in conn.execute('SELECT session_id,survey_id,status,completion_percentage FROM interview_sessions').fetchall()]
print(f"Total: {len(sessions)}")
for s in sessions[:10]:
    hc = conn.execute('SELECT COUNT(*) FROM conversation_history WHERE session_id=?',(s['session_id'],)).fetchone()[0]
    print(f"  sid={s['session_id'][:20]} survey={s['survey_id']} status={s['status']} comp={s['completion_percentage']}% hist={hc}")

print("\n=== RESPONSES ===")
print(f"Total: {conn.execute('SELECT COUNT(*) FROM responses').fetchone()[0]}")
for r in [dict(r) for r in conn.execute('SELECT id,session_id,question_id,answer_text FROM responses ORDER BY created_at DESC LIMIT 10').fetchall()]:
    print(f"  id={r['id']} session={str(r.get('session_id',''))[:15]} q={r.get('question_id','?')} answer={str(r.get('answer_text',''))[:40]}")

print("\n=== SURVEY_RESPONDENTS ===")
print(f"Total: {conn.execute('SELECT COUNT(*) FROM survey_respondents').fetchone()[0]}")
for sr in [dict(r) for r in conn.execute('SELECT survey_id,respondent_id,status,session_id FROM survey_respondents ORDER BY rowid DESC LIMIT 10').fetchall()]:
    print(f"  survey={sr['survey_id']} resp={sr['respondent_id']} status={sr['status']} session={str(sr.get('session_id',''))[:15]}")

# Check table schema for responses
print("\n=== RESPONSES TABLE SCHEMA ===")
for col in conn.execute("PRAGMA table_info(responses)").fetchall():
    print(f"  {dict(col)['name']} ({dict(col)['type']})")

# Check table schema for conversation_history
print("\n=== CONVERSATION_HISTORY SCHEMA ===")
for col in conn.execute("PRAGMA table_info(conversation_history)").fetchall():
    print(f"  {dict(col)['name']} ({dict(col)['type']})")

conn.close()
