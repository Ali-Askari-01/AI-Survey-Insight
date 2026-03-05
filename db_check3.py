import sqlite3
conn = sqlite3.connect('data/survey_engine.db')
conn.row_factory = sqlite3.Row

sessions = conn.execute('''
    SELECT s.session_id, s.survey_id, s.status, s.completion_percentage, 
           (SELECT COUNT(*) FROM conversation_history WHERE session_id = s.session_id) as hist_count
    FROM interview_sessions s 
    WHERE s.status IN ('completed', 'completing', 'active')
    ORDER BY s.survey_id
''').fetchall()

for s in sessions:
    d = dict(s)
    sid = d["session_id"][:12]
    print(f"survey={d['survey_id']} session={sid}... status={d['status']} comp={d['completion_percentage']}% hist={d['hist_count']}")

conn.close()
