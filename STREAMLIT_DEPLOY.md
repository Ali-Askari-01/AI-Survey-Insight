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

## Notes

- If `GEMINI_API_KEY` is missing, AI generation falls back to non-AI defaults where available.
- SQLite data persists only as long as your Streamlit environment storage persists.
- For production persistence, set `DATA_DIR` to a mounted persistent path.
