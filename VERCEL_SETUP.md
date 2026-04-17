# Vercel Setup (Root Deployment)

This repository is now configured to deploy from the repo root (`./`) while serving the static legacy frontend from `frontend_legacy`.

## Why Vercel showed Next.js services

Vercel auto-detected `frontend` and `frontend_nextjs` as Next.js apps because both folders contain Next.js files.

## What was fixed

- Added root `vercel.json` to force static routing to `frontend_legacy`.
- Added root API proxy function `api/[...path].js` for `/api/*` requests.
- Added `.vercelignore` to exclude `frontend` and `frontend_nextjs` from deployment upload, preventing Next.js service auto-detection.

## Required environment variable

Set this in Vercel Project Settings:

- `BACKEND_URL=https://your-fastapi-domain`

Example: `https://your-app.up.railway.app`

## Important notes

- WebSocket (`/ws/*`) is not proxied in this serverless proxy setup.
- FastAPI + SQLite stay on your backend host.
- Vercel serves frontend only and forwards API HTTP traffic.
