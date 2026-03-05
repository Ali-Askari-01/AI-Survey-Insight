import sqlite3
import sys
sys.path.insert(0, '.')
from backend.auth import verify_password

conn = sqlite3.connect('data/survey_engine.db')
conn.row_factory = sqlite3.Row
users = conn.execute('SELECT id, email, password_hash FROM users LIMIT 5').fetchall()

for u in users:
    d = dict(u)
    ph = d['password_hash']
    fmt = 'salted' if ':' in str(ph) else 'legacy'
    ok = verify_password('admin123', ph)
    ok2 = verify_password('password123', ph)
    ok3 = verify_password('test1234', ph)
    print(f"ID={d['id']} email={d['email']} fmt={fmt} admin123={ok} password123={ok2} test1234={ok3}")

conn.close()
