# Instructions: Set Your Account as Founder

## Quick Database Update (Run this in your terminal):

```bash
# 1. Open SQLite database
sqlite3 "data/survey_engine.db"

# 2. Check current users and their roles
.headers on
SELECT id, email, role FROM users;

# 3. Update your account to founder role (replace YOUR_EMAIL)
UPDATE users SET role = 'founder' WHERE email = 'YOUR_EMAIL@example.com';

# 4. Verify the change
SELECT id, email, role FROM users WHERE email = 'YOUR_EMAIL@example.com';

# 5. Exit
.quit
```

## Alternative: Python Script Method

```python
import sqlite3

# Connect to database
conn = sqlite3.connect('data/survey_engine.db')
cursor = conn.cursor()

# Update your email to founder role
your_email = "YOUR_EMAIL@example.com"  # Replace with your actual email
cursor.execute("UPDATE users SET role = 'founder' WHERE email = ?", (your_email,))
conn.commit()

# Verify
cursor.execute("SELECT email, role FROM users WHERE email = ?", (your_email,))
result = cursor.fetchone()
print(f"Updated: {result[0]} is now {result[1]}")

conn.close()
```

## Available User Roles:
- **pm** (product manager) - Default role
- **founder** - Full access including analytics dashboard  
- **admin** - Full access including analytics dashboard
- **engineer** - Development access