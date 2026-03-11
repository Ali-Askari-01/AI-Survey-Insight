import requests, json, uuid

s = requests.Session()
BASE = 'http://localhost:8000'
u = uuid.uuid4().hex[:6]
results = []

def check(name, ok):
    status = "PASS" if ok else "FAIL"
    results.append(f"[{status}] {name}")
    print(f"[{status}] {name}")

# Auth
r = s.post(f'{BASE}/api/auth/register', json={'name':'T','email':f't_{u}@t.com','password':'Test1234!'})
token = r.json().get('access_token','')
h = {'Authorization': f'Bearer {token}'}
check("Auth", bool(token))

# Create survey + questions
r2 = s.post(f'{BASE}/api/surveys/', json={'title':'Quick Test','description':'Test'}, headers=h)
sid = r2.json()['id']
for i, q in enumerate(['Q1 experience?','Q2 features?','Q3 suggestions?']):
    s.post(f'{BASE}/api/surveys/questions', json={'survey_id':sid,'question_text':q,'question_type':'open','order_index':i}, headers=h)

# Publish
r3 = s.post(f'{BASE}/api/publish/', json={'survey_id':sid,'require_email':False}, headers=h)
sc = r3.json()['share_code']
check("Publish", bool(sc))

# Anonymous join (Feature 5)
r5 = s.post(f'{BASE}/api/publish/join', json={'email':f'a_{u}@r.local','name':'Anon','share_code':sc,'channel':'web-form'})
sess = r5.json().get('session_id','')
check("Anonymous Join (Feature 5)", bool(sess))

# Get questions
qs = s.get(f'{BASE}/api/surveys/{sid}', headers=h).json().get('questions',[])
check("Questions loaded", len(qs) == 3)

# Translation (Feature 3)
r8 = s.post(f'{BASE}/api/interviews/translate', json={'texts':['Hello world'],'target_language':'ur'})
trans = r8.json().get('translations',[])
check("Translation endpoint (Feature 3)", len(trans) > 0 and trans[0] != 'Hello world')

# Same-language bypass
r9 = s.post(f'{BASE}/api/interviews/translate', json={'texts':['Hello'],'target_language':'en','source_language':'en'})
same = r9.json().get('translations',[])
check("Same-language bypass", same == ['Hello'])

# Frontend HTML checks for all 6 features
html = s.get(f'{BASE}/interview/{sc}').text
feature_markers = {
    'Feature 1 - Progress': 'chat-progress-bar',
    'Feature 2 - Summary': 'topic-pills',
    'Feature 3 - Translation': 'lang-selector',
    'Feature 4 - Emoji': 'emoji-reactions',
    'Feature 5 - Anonymous': 'handleAnonymousJoin',
    'Feature 6 - Pause/Resume': '_pauseInterview',
}
for name, marker in feature_markers.items():
    check(f"HTML: {name}", marker in html)

# Additional markers
for marker in ['_translateTexts','_getSavedSession','_showResumePrompt','_updateChatProgress','emoji-btn','pause-btn','resume-card','summary-box']:
    check(f"HTML marker: {marker}", marker in html)

print("\n" + "="*50)
passed = sum(1 for r in results if '[PASS]' in r)
print(f"Results: {passed}/{len(results)} passed")
print("="*50)
