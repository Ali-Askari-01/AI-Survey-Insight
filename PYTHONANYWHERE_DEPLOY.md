# PythonAnywhere Deployment Setup

This project is prepared for PythonAnywhere with a WSGI adapter and static frontend serving.

## Files added for PythonAnywhere

- `pythonanywhere_app.py`: wraps existing FastAPI app and mounts `static/` at `/`.
- `pythonanywhere_wsgi.py`: exposes `application` WSGI callable via `a2wsgi`.
- `static/`: frontend files copied from `frontend_legacy/`.

## PythonAnywhere Web app configuration

1. Create a Python web app (manual configuration, Python 3.12 if available).
2. In Bash console:
   - `cd ~/AI-Survey-Insight`
   - `python -m venv .venv`
   - `source .venv/bin/activate`
   - `pip install -r requirements.txt`
3. Open the WSGI configuration file in PythonAnywhere.
4. Replace its content with:

```python
import sys
path = '/home/<your-username>/AI-Survey-Insight'
if path not in sys.path:
    sys.path.insert(0, path)

from pythonanywhere_wsgi import application
```

5. In the PythonAnywhere Web tab:
   - Set **Working directory** to `/home/<your-username>/AI-Survey-Insight`
   - Set **Virtualenv** to `/home/<your-username>/AI-Survey-Insight/.venv`
6. Add environment variables in PythonAnywhere (Web tab -> Environment variables):
   - `GEMINI_API_KEY`
   - `ASSEMBLYAI_API_KEY`
   - `JWT_SECRET`
   - `GOOGLE_CLIENT_ID`
   - `GOOGLE_CLIENT_SECRET`
   - `GOOGLE_REDIRECT_URI`
7. Reload the web app.

## Verify URLs

- `/` -> landing page from `static/landing.html`
- `/app` -> main app shell
- `/health` -> backend health endpoint
- `/api/auth/google/login` -> Google OAuth entry
