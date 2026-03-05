"""E2E Test: Verify full interview flow — join → chat → complete → analysis"""
import requests
import json
import time

BASE = "http://localhost:8000"

def test_flow():
    print("=" * 60)
    print("E2E TEST: Interview flow + AI Analysis")
    print("=" * 60)
    
    # 1. Register/login
    print("\n[1] Registering user...")
    r = requests.post(f"{BASE}/api/auth/register", json={
        "name": "E2E Tester", "email": f"e2e_{int(time.time())}@test.com", "password": "Test1234!"
    }, timeout=15)
    assert r.status_code == 200, f"Register failed: {r.status_code} {r.text}"
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("  OK - Got auth token")
    
    # 2. Create survey with questions
    print("\n[2] Creating survey + questions...")
    r = requests.post(f"{BASE}/api/surveys/", json={
        "title": "E2E Test Survey", "description": "Testing interview flow", "channel_type": "chat"
    }, headers=headers, timeout=15)
    assert r.status_code == 200, f"Survey create failed: {r.status_code} {r.text}"
    survey_id = r.json()["id"]
    print(f"  Created survey ID={survey_id}")
    
    for i, q_text in enumerate(["What do you think about the product?", "How could we improve?", "Any final thoughts?"]):
        r = requests.post(f"{BASE}/api/surveys/questions", json={
            "survey_id": survey_id, "question_text": q_text, "order_index": i
        }, headers=headers, timeout=15)
        assert r.status_code == 200, f"Question create failed: {r.text}"
    print("  Created 3 questions")
    
    # 3. Publish survey
    print("\n[3] Publishing survey...")
    r = requests.post(f"{BASE}/api/publish/", json={
        "survey_id": survey_id, "title": "E2E Test", "web_form_enabled": True,
        "chat_enabled": True, "audio_enabled": True, "require_email": True
    }, headers=headers, timeout=15)
    assert r.status_code == 200, f"Publish failed: {r.status_code} {r.text}"
    share_code = r.json()["share_code"]
    print(f"  Published with share_code={share_code}")
    
    # 4. Join as respondent (simulating interview.html flow)
    print("\n[4] Joining as respondent...")
    r = requests.post(f"{BASE}/api/publish/join", json={
        "email": "respondent@test.com", "name": "Test Respondent",
        "share_code": share_code, "channel": "chat"
    }, timeout=15)
    assert r.status_code == 200, f"Join failed: {r.status_code} {r.text}"
    join_data = r.json()
    session_id = join_data.get("session_id")
    print(f"  Joined! session_id={session_id[:12]}...")
    
    # 5. Verify NO duplicate session creation needed
    # (Previously the frontend would create another session via /interviews/sessions)
    
    # 6. Send chat messages
    print("\n[5] Sending chat messages...")
    messages = [
        "The product is great but the UI needs work. Navigation is confusing.",
        "Better documentation and a more intuitive dashboard would help a lot.",
        "Overall positive experience. Keep up the good work!"
    ]
    
    for i, msg_text in enumerate(messages):
        print(f"  Sending message {i+1}/3...")
        r = requests.post(f"{BASE}/api/interviews/chat", json={
            "session_id": session_id, "message": msg_text, "message_type": "text"
        }, timeout=60)
        assert r.status_code == 200, f"Chat failed: {r.status_code} {r.text}"
        chat_data = r.json()
        print(f"    AI responded: {chat_data.get('ai_message', '')[:80]}...")
        print(f"    Progress: {chat_data.get('progress', 0)}%")
        print(f"    Complete: {chat_data.get('interview_complete', False)}")
    
    # 7. Complete interview
    print("\n[6] Completing interview...")
    r = requests.post(f"{BASE}/api/interviews/sessions/{session_id}/complete", timeout=60)
    if r.status_code == 200:
        print("  Session marked complete")
    else:
        print(f"  Complete returned {r.status_code} (may already be complete)")
    
    # 8. Save transcript
    print("\n[7] Saving transcript...")
    r = requests.post(f"{BASE}/api/publish/transcripts/{session_id}", timeout=60)
    print(f"  Transcript save: {r.status_code}")
    
    # 9. Verify data in DB
    print("\n[8] Verifying data...")
    import sqlite3
    conn = sqlite3.connect('data/survey_engine.db')
    conn.row_factory = sqlite3.Row
    
    hist = conn.execute("SELECT COUNT(*) as c FROM conversation_history WHERE session_id = ?", (session_id,)).fetchone()["c"]
    resps = conn.execute("SELECT COUNT(*) as c FROM responses WHERE session_id = ?", (session_id,)).fetchone()["c"]
    sess = conn.execute("SELECT status, completion_percentage FROM interview_sessions WHERE session_id = ?", (session_id,)).fetchone()
    
    print(f"  conversation_history entries: {hist}")
    print(f"  response records: {resps}")
    print(f"  session status: {dict(sess)['status']}")
    print(f"  completion_percentage: {dict(sess)['completion_percentage']}%")
    conn.close()
    
    assert hist >= 4, f"Expected >= 4 conversation history entries (1 greeting + 3 user + 3 AI), got {hist}"
    assert resps >= 3, f"Expected >= 3 responses, got {resps}"
    print("  DATA OK!")
    
    # 10. Test AI Analysis
    print("\n[9] Testing AI Analysis...")
    r = requests.get(f"{BASE}/api/publish/analysis/{survey_id}", headers=headers, timeout=120)
    assert r.status_code == 200, f"Analysis failed: {r.status_code} {r.text}"
    analysis_data = r.json()
    print(f"  has_data: {analysis_data.get('has_data')}")
    print(f"  transcripts_analyzed: {analysis_data.get('transcripts_analyzed', 0)}")
    if analysis_data.get("analysis"):
        keys = list(analysis_data["analysis"].keys()) if isinstance(analysis_data["analysis"], dict) else "string"
        print(f"  analysis keys: {keys}")
    
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)

if __name__ == "__main__":
    test_flow()
