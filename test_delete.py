import requests, uuid

s = requests.Session()
BASE = 'http://localhost:8000'
u = uuid.uuid4().hex[:6]

# Auth
r = s.post(f'{BASE}/api/auth/register', json={'name':'D','email':f'd_{u}@t.com','password':'Test1234!'})
token = r.json().get('access_token','')
h = {'Authorization': f'Bearer {token}'}

# Create survey + questions
r2 = s.post(f'{BASE}/api/surveys/', json={'title':'Delete Test Survey','description':'To be deleted'}, headers=h)
sid = r2.json()['id']
for i, q in enumerate(['Q1?','Q2?']):
    s.post(f'{BASE}/api/surveys/questions', json={'survey_id':sid,'question_text':q,'question_type':'open','order_index':i}, headers=h)

# Publish
r3 = s.post(f'{BASE}/api/publish/', json={'survey_id':sid,'require_email':False}, headers=h)
sc = r3.json()['share_code']
print(f'Created survey {sid}, share_code={sc}')

# Verify it exists
r4 = s.get(f'{BASE}/api/surveys/{sid}', headers=h)
print(f'Survey exists: {r4.status_code}')

# Delete it
r5 = s.delete(f'{BASE}/api/surveys/{sid}', headers=h)
print(f'Delete: {r5.status_code} - {r5.json()}')

# Verify it's gone
r6 = s.get(f'{BASE}/api/surveys/{sid}', headers=h)
print(f'After delete: {r6.status_code} (should be 404)')

# Verify publication is also gone
r7 = s.get(f'{BASE}/api/publish/s/{sc}')
print(f'Publication after delete: {r7.status_code} (should be 404)')

print('ALL TESTS PASSED')
