# CLAUDE.md

Christmas gift lottery (Secret Santa). Users sign up and log in, one "lottery master" runs the draw, and each user sees who they should buy a gift for and can email themselves the result. UI text is Polish. Plan and decisions: [docs/refactor-plan.md](docs/refactor-plan.md).

## Structure

- `frontend/`: Nuxt 3 SPA (`ssr: false`) with `@nuxt/ui` and `@supabase/supabase-js`. Managed with **yarn**.
  - `pages/index.vue` login, `pages/rejestracja.vue` sign-up, `pages/panel.vue` personal page.
  - `middleware/auth.global.ts`: logged out goes to `/`; logged in on `/` or `/rejestracja` goes to `/panel`.
  - `plugins/supabase.client.ts` holds the client and session; `composables/useAuth.ts` handles login and logout; `composables/useApi.ts` calls the backend with a Bearer token.
- `backend/`: FastAPI, managed with **uv**. Its modules:
  - `app/main.py` (the `/api` prefix, CORS, lifespan pool), `config.py`, `db.py` (psycopg async pool).
  - `auth.py` verifies the Supabase JWT (JWKS, ES256) and provides `require_master`.
  - `supabase_admin.py` creates users through the admin API.
  - `draw.py` is the pairing algorithm. `email.py` sends mail through the Brevo HTTP API.
  - `routers/auth.py`, `me.py`, `lottery.py`.
- `supabase/migrations/0001_init.sql`: schema.
- `vercel.json`: one Vercel project with two Services, `frontend` (static SPA) and `backend` (FastAPI). `/api/*` goes to the backend, everything else to the frontend.

## Commands

```bash
# backend (run from backend/)
uv sync
uv run uvicorn app.main:app --reload --port 8000
uv run pytest
uv run ruff check .

# frontend (run from frontend/; never from the repo root)
yarn install
yarn dev            # http://localhost:3000
yarn generate       # static build -> .output/public
npx nuxi typecheck
```

## Environment

- `backend/.env` (see `.env.example`): `SUPABASE_URL` (project URL only, no path), `SUPABASE_SERVICE_ROLE_KEY`, `DATABASE_URL` (Session pooler locally, Transaction pooler on Vercel), `BREVO_API_KEY`, `EMAIL_SENDER_ADDRESS` (verified in Brevo), `EMAIL_SENDER_NAME`, `CORS_ORIGINS` (comma-separated, no trailing slash), `MIN_PARTICIPANTS` (default 3), `EMAIL_COOLDOWN_MINUTES` (default 10).
- `frontend/.env` (see `.env.example`): `NUXT_PUBLIC_SUPABASE_URL`, `NUXT_PUBLIC_SUPABASE_ANON_KEY` (publishable key), `NUXT_PUBLIC_API_BASE` (for example `http://localhost:8000/api`).
- Never commit `.env` files or the service role key.

## Data model

- `profiles` (one per auth user: `username`, `is_master`), `lotteries` (`status`: `finished` or `cancelled`), `lottery_results` (giver, receiver), `lottery_logs` (every action with `lottery_id`).
- Partial unique indexes enforce one master (`profiles_single_master`), one active lottery (`lotteries_single_active`) and unique usernames ignoring case (`profiles_username_ci`).
- RLS is on with no policies, so only the backend (service role) reads and writes the tables. Public sign-up is disabled in Supabase; users are created through `POST /api/auth/register`.
- Cancelling a lottery is a soft cancel (status `cancelled`), so old ids and logs stay queryable.

## API (prefix `/api`)

`GET /health`, `GET /auth/master-available`, `POST /auth/register` (409: `email_taken`, `username_taken`, `master_taken`), `GET /me`, `GET /lottery/current`, `GET /participants` (master), `POST /lottery` (master; 400 `not_enough_participants`, 409 `lottery_active`), `DELETE /lottery/current` (master), `POST /lottery/current/email` (404 `no_result`, 429 `rate_limited`, 502 `email_failed`).

## Gotchas

- Everyone, including the master, takes part in the draw. Users registering after the draw are not in it.
- Test emails must use a real-looking domain such as `example.com`; `.test` is rejected by validation.
- Emails need Brevo configured, otherwise the email endpoint returns 502.
- Backend tests use a scripted fake DB connection and dummy env vars (`tests/conftest.py`); they don't touch Supabase.
- The backend runs on Vercel Fluid compute: each instance has its own small pool (`min_size=0`, `max_size=3`, `prepare_threshold=None` for the Transaction pooler), and shutdown cleanup must finish within 500 ms (`pool.close(timeout=0.3)`).
- Free tiers: Vercel Hobby is non-commercial and functions have cold starts; a Supabase project pauses after 7 days without activity.
- Vercel Services is in beta.
- Multiple groups are not supported yet (planned as a later stage).

## Deployment

1. Vercel: import the repo with root directory = repository root (`vercel.json` defines the services).
2. Env vars (shared by both services): `NUXT_PUBLIC_SUPABASE_URL`, `NUXT_PUBLIC_SUPABASE_ANON_KEY`, `NUXT_PUBLIC_API_BASE=/api`, and the backend vars with `DATABASE_URL` set to the Transaction pooler (port 6543).
3. Frontend and API share one origin, so `CORS_ORIGINS` only matters locally.
