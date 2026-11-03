# Losowanie prezentów

Christmas gift lottery (Secret Santa). Users register, one lottery master starts the draw, and everyone sees who they should buy a gift for. The result can be emailed to the user.

Stack: Nuxt 3 (Vercel), FastAPI (Render), Supabase (Auth and Postgres), Brevo (email).

## 1. Supabase

1. Create a project.
2. Authentication → Sign In / Providers → Email: turn off "Enable email provider" sign-ups and "Secure email change" (users are created by the backend).
3. Run `supabase/migrations/0001_init.sql` in the SQL editor.
4. Collect: project URL, publishable (anon) key, service role key, and the Session pooler connection string (Connect → Session pooler).

## 2. Brevo

Create an account, verify a sender address, and create an API key.

## 3. Run locally

Backend:

```bash
cd backend
cp .env.example .env    # fill it in
uv sync
uv run uvicorn app.main:app --reload --port 8000
uv run pytest
```

Frontend:

```bash
cd frontend
cp .env.example .env    # fill it in
yarn install
yarn dev                # http://localhost:3000
```

## 4. Deploy

1. Render: New → Blueprint, select this repo. Fill in the secret env vars from `backend/.env.example`. Leave `CORS_ORIGINS` empty for now.
2. Vercel: import the repo with root directory `frontend`. Set `NUXT_PUBLIC_SUPABASE_URL`, `NUXT_PUBLIC_SUPABASE_ANON_KEY` and `NUXT_PUBLIC_API_BASE=https://<service>.onrender.com/api`.
3. Set `CORS_ORIGINS` on Render to the Vercel URL (no trailing slash) and redeploy.

Free-tier limits: Render sleeps after 15 minutes idle (the first request takes about a minute), and a Supabase project pauses after 7 days without activity.

## Checking a lottery

Every lottery has an id. In Supabase, `lotteries` holds the status (`finished` or `cancelled`) and `lottery_logs` records each action with its `lottery_id`.
