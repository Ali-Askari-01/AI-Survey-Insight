# Vercel Deployment (Legacy Frontend)

This project currently serves a static HTML/CSS/JS frontend from `frontend_legacy`, with FastAPI + SQLite running separately.

## 1) Create Vercel Project

1. Import this GitHub repository into Vercel.
2. Set **Root Directory** to `frontend_legacy`.
3. Framework preset can be `Other`.

## 2) Environment Variables

Set this required env var in Vercel Project Settings:

- `BACKEND_URL` = your FastAPI public URL (example: `https://your-app.up.railway.app`)

The file `api/[...path].js` proxies all frontend `/api/*` calls to `${BACKEND_URL}/api/*`.

## 3) Routes

`vercel.json` is configured to support:

- `/` -> landing page
- `/app` -> main app (`index.html`)
- `/survey-form`, `/survey-chat`, `/survey-audio`
- `/interview/:shareCode` and `/interview/:shareCode/:channel`

## 4) Notes

- WebSocket (`/ws/*`) is not proxied by Vercel Serverless Functions in this setup. Core API features work through HTTP.
- Keep FastAPI + SQLite hosted on your backend provider (Railway/Docker host), and use Vercel for frontend delivery.
