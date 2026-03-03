"""Debug script for AI Analysis and Response Registration issues."""
import requests
import json
import sys

BASE = "http://localhost:8000"

# --- Auth ---
print("=== Auth ===")
r = requests.post(f"{BASE}/api/auth/login", json={"email": "debug2@test.com", "password": "Test1234!"}, timeout=10)
if r.status_code != 200:
    r = requests.post(f"{BASE}/api/auth/register", json={"email": "debug4@test.com", "password": "Test1234!", "name": "Debug4"}, timeout=10)
token = r.json().get("access_token", "")
if not token:
    print("FATAL: Cannot get auth token")
    sys.exit(1)
h = {"Authorization": f"Bearer {token}"}
print(f"Token obtained: {token[:30]}...")

# --- List Surveys ---
print("\n=== Surveys ===")
resp = requests.get(f"{BASE}/api/surveys/", headers=h, timeout=10)
print(f"Status: {resp.status_code}")
surveys = resp.json() if resp.status_code == 200 else []
for s in surveys[:10]:
    print(f"  ID={s['id']} | Title={s.get('title', '?')[:40]} | Status={s.get('status', '?')}")

# --- Test AI Analysis on each survey ---
print("\n=== AI Analysis Test ===")
for s in surveys[:5]:
    sid = s["id"]
    print(f"\nTesting /publish/analysis/{sid} ({s.get('title', '?')[:30]})")
    try:
        ra = requests.get(f"{BASE}/api/publish/analysis/{sid}", headers=h, timeout=60)
        print(f"  Status: {ra.status_code}")
        if ra.status_code != 200:
            print(f"  Error: {ra.text[:300]}")
        else:
            data = ra.json()
            print(f"  has_data={data.get('has_data')} transcripts={data.get('transcripts_analyzed', 0)}")
    except Exception as e:
        print(f"  Exception: {e}")

# --- Check interview sessions & response data ---
print("\n=== Interview Sessions & Responses ===")
import sqlite3
conn = sqlite3.connect("data/survey_engine.db")
conn.row_factory = sqlite3.Row

sessions = conn.execute("SELECT session_id, survey_id, status, completion_percentage FROM interview_sessions ORDER BY created_at DESC LIMIT 10").fetchall()
print(f"Total sessions: {conn.execute('SELECT COUNT(*) FROM interview_sessions').fetchone()[0]}")
for s in sessions:
    sd = dict(s)
    hist_count = conn.execute("SELECT COUNT(*) FROM conversation_history WHERE session_id = ?", (sd['session_id'],)).fetchone()[0]
    resp_count = conn.execute("SELECT COUNT(*) FROM responses WHERE session_id = ?", (sd['session_id'],)).fetchone()[0]
    print(f"  Session={sd['session_id'][:20]}... survey={sd['survey_id']} status={sd['status']} completion={sd['completion_percentage']}% hist={hist_count} resp={resp_count}")

# Check for responses table structure
print("\n=== Responses Table ===")
resp_count_total = conn.execute("SELECT COUNT(*) FROM responses").fetchone()[0]
print(f"Total responses: {resp_count_total}")
recent = conn.execute("SELECT * FROM responses ORDER BY created_at DESC LIMIT 5").fetchall()
for r in recent:
    rd = dict(r)
    print(f"  id={rd['id']} session={rd.get('session_id', '?')[:20]} q_id={rd.get('question_id', '?')} answer={str(rd.get('answer_text', ''))[:50]}")

# Check survey_respondents table
print("\n=== Survey Respondents ===")
sr_count = conn.execute("SELECT COUNT(*) FROM survey_respondents").fetchone()[0]
print(f"Total: {sr_count}")
srs = conn.execute("SELECT * FROM survey_respondents ORDER BY rowid DESC LIMIT 10").fetchall()
for sr in srs:
    srd = dict(sr)
    print(f"  survey={srd.get('survey_id')} respondent={srd.get('respondent_id')} status={srd.get('status')} session={str(srd.get('session_id', ''))[:20]}")

conn.close()
print("\n=== Done ===")
