# Streamlit Deployment Guide

This repository can now run as a Streamlit app using `streamlit_app.py`.

## What was set up

- Streamlit entrypoint: `streamlit_app.py`
- Streamlit config: `.streamlit/config.toml`
- Secrets template: `.streamlit/secrets.toml.example`
- App uses existing backend service layer directly (`backend/*`) and SQLite DB.

## Local run

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Add secrets (optional for AI features):
   - Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`
   - Fill your API keys.
3. Start Streamlit:
   ```bash
   streamlit run streamlit_app.py
   ```

## Streamlit Cloud deployment

1. Push this repository to GitHub.
2. In Streamlit Cloud, create a new app:
   - Main file path: `streamlit_app.py`
3. In app **Secrets**, add keys from `.streamlit/secrets.toml.example`.
4. Deploy.

## Streamlit Cloud checklist (repo-specific)

Before clicking deploy, verify:

1. **Main file path** is set to `streamlit_app.py`.
2. **Python version** uses `runtime.txt` (`python-3.11`).
3. **Secrets** include at least:
    - `GEMINI_API_KEY` (AI generation)
    - `ASSEMBLYAI_API_KEY` (voice features)
    - `JWT_SECRET` (recommended)
4. **Persistent data path**:
    - Set `DATA_DIR` to a mounted persistent path if available.
    - If not set, default local storage can reset between deploys/restarts.
5. **Smoke test after deploy**:
    - Open **Health Check** tab in the app.
    - Confirm DB connectivity reports healthy.
    - Run **AI smoke test** button and confirm output is returned.

## Troubleshooting

- **Import "streamlit" could not be resolved**:
   - Install dependencies with `pip install -r requirements.txt`.
- **AI features fail**:
   - Recheck `GEMINI_API_KEY` in Streamlit secrets.
- **No data after restart**:
   - Configure `DATA_DIR` to persistent storage.
- **DB path confusion**:
   - Use the **Health Check** tab to see active DB and data directory at runtime.

## Notes

- If `GEMINI_API_KEY` is missing, AI generation falls back to non-AI defaults where available.
- SQLite data persists only as long as your Streamlit environment storage persists.
- For production persistence, set `DATA_DIR` to a mounted persistent path.
