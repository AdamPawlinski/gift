# Refactor plan: Christmas gift lottery

## Context

Today the app is a single Nuxt page. The participants are hardcoded in `assets/participants.json`, the draw runs in the browser, the results are lost on reload, and emails go out through EmailJS from the frontend. The goal is a multi-user app with these parts:

- Registration and login (Supabase Auth).
- A personal panel for each user.
- One lottery master who starts and cancels the draw.
- A Python backend that runs the draw and stores the results and logs in Supabase.

## Decisions

| Topic | Decision |
|---|---|
| Frontend | Nuxt 3 + `@nuxt/ui`, SPA mode (`ssr: false`), deployed as a static site on Vercel |
| Backend | Python 3.12, FastAPI, managed with `uv`, deployed on Vercel as a FastAPI service (Vercel Services, same project as the frontend) |
| Database | Supabase Postgres (free tier) |
| Auth | Supabase Auth with email + password. Sign-up goes only through the backend. The frontend uses `supabase-js` only for `signInWithPassword` and `signOut`, and for refreshing the session. The backend verifies the Supabase JWT. |
| DB access from backend | `psycopg` 3 (async) through the Supabase **Session pooler** URL (IPv4). Transactions are explicit. |
| Auth admin from backend | `supabase` Python client with the service-role key, used for creating and deleting users |
| Lottery master | First come, first served. At most one master, enforced by a partial unique index. |
| Email | Sent by the backend through the Brevo transactional HTTP API. It's free (300 emails/day) and needs only a verified sender address. An HTTP API avoids SMTP from serverless functions. |
| Table access | RLS is enabled on every public table with no policies, so only the backend (service role) reads and writes data |

## Scope

- Every registered user, including the master, takes part in the draw.
- One group and one active lottery at a time. Multiple groups (e.g. per family) are the next stage and out of scope here. To keep that migration cheap, all queries go through the backend only and no table is exposed to the client.
- Accounts already exist on Supabase and Vercel. A Brevo account is still to be created (step 8).

## Additional features (proposed, included in the plan)

1. **Participant list for the master**: the panel shows "Uczestnicy (N): …" so the master can see who registered before starting the draw.
2. **Minimum of 3 participants** for a draw. With 2 people, each one knows who drew them. The limit is configurable via `MIN_PARTICIPANTS`.
3. **Late registration**: someone who registers after a draw sees "Losowanie odbyło się przed Twoją rejestracją. Poproś mistrza losowania o ponowne losowanie."
4. **Confirmation modals** before "uruchom losowanie" and "kasuj wyniki losowania".
5. **Master slot hint on sign-up**: when a master already exists, the "Tak" answer is disabled and labelled "Mistrz losowania już istnieje". The backend still enforces this on its own.
6. **Soft reset**: "kasuj wyniki losowania" sets the lottery `status = 'cancelled'` instead of deleting it. Results and logs stay queryable by `lottery_id`.
7. **Audit log table** `lottery_logs` for `user_registered`, `lottery_started`, `lottery_cancelled` and `result_email_sent`.
8. **Email rate limit**: one result email per user per 10 minutes.
9. **Route guards**: logged-out users are redirected to `/`, and logged-in users are redirected from `/` and `/rejestracja` to `/panel`.
10. **Cleanup**: remove `assets/participants.json` (personal data), EmailJS, `rfdc` and `script/`.

## Target structure

```
gift/
  frontend/                 # Nuxt app (moved from repo root)
    app.vue
    nuxt.config.ts
    layouts/default.vue
    plugins/supabase.client.ts
    composables/useAuth.ts
    composables/useApi.ts
    middleware/auth.global.ts
    pages/index.vue         # login
    pages/rejestracja.vue   # sign-up
    pages/panel.vue         # user panel
    .env.example
  backend/
    pyproject.toml
    app/
      main.py               # FastAPI app, CORS, routers
      config.py             # pydantic-settings
      db.py                 # psycopg async pool
      auth.py               # JWT verification dependency
      supabase_admin.py     # service-role client
      draw.py               # pure draw algorithm
      email.py              # Brevo sender
      schemas.py            # pydantic models
      routers/auth.py
      routers/me.py
      routers/lottery.py
    tests/
      test_draw.py
      test_api.py
    .env.example
  supabase/
    migrations/0001_init.sql
  docs/refactor-plan.md
  CLAUDE.md
  vercel.json
```

## Database schema (`supabase/migrations/0001_init.sql`)

```sql
create table public.profiles (
  id          uuid primary key references auth.users(id) on delete cascade,
  username    text not null,
  email       text not null,
  is_master   boolean not null default false,
  created_at  timestamptz not null default now()
);
create unique index profiles_username_ci on public.profiles (lower(username));
create unique index profiles_single_master on public.profiles (is_master) where is_master;

create table public.lotteries (
  id            uuid primary key default gen_random_uuid(),
  status        text not null check (status in ('finished','cancelled')),
  started_by    uuid not null references public.profiles(id),
  created_at    timestamptz not null default now(),
  cancelled_by  uuid references public.profiles(id),
  cancelled_at  timestamptz
);
create unique index lotteries_single_active on public.lotteries (status) where status = 'finished';

create table public.lottery_results (
  lottery_id   uuid not null references public.lotteries(id) on delete cascade,
  giver_id     uuid not null references public.profiles(id) on delete cascade,
  receiver_id  uuid not null references public.profiles(id) on delete cascade,
  primary key (lottery_id, giver_id),
  unique (lottery_id, receiver_id),
  check (giver_id <> receiver_id)
);

create table public.lottery_logs (
  id          bigint generated always as identity primary key,
  lottery_id  uuid references public.lotteries(id),
  actor_id    uuid references public.profiles(id) on delete set null,
  action      text not null check (action in ('user_registered','lottery_started','lottery_cancelled','result_email_sent')),
  details     jsonb not null default '{}',
  created_at  timestamptz not null default now()
);

alter table public.profiles        enable row level security;
alter table public.lotteries       enable row level security;
alter table public.lottery_results enable row level security;
alter table public.lottery_logs    enable row level security;
```

A lottery with `status = 'finished'` is the active one, and there is at most one. "Not started" means no row has `status = 'finished'`.

## Backend API

All endpoints are under the `/api` prefix. Every endpoint except `health`, `auth/register` and `auth/master-available` requires `Authorization: Bearer <supabase access token>`.

| Method | Path | Access | Behavior |
|---|---|---|---|
| GET | `/health` | public | `{"status":"ok"}` |
| GET | `/auth/master-available` | public | `{"available": bool}` |
| POST | `/auth/register` | public | Body `{email, password, username, is_master}`. Returns 201 `{id}`. Returns 409 with `detail` set to `email_taken`, `username_taken` or `master_taken`, and 422 for validation errors. |
| GET | `/me` | user | `{id, username, email, is_master}` |
| GET | `/lottery/current` | user | `{status: "not_started"\|"finished", lottery_id, participated: bool, receiver_username: str\|null}` |
| GET | `/participants` | master | `[{username}]` sorted by `created_at` |
| POST | `/lottery` | master | Runs the draw over all profiles. Returns 201 `{lottery_id}`. Returns 409 `lottery_active` if a finished lottery already exists, and 400 `not_enough_participants` if there are too few. |
| DELETE | `/lottery/current` | master | Sets `status='cancelled'`, `cancelled_by` and `cancelled_at`, and writes a log entry. Returns 204, or 404 `no_active_lottery`. |
| POST | `/lottery/current/email` | user | Emails the user their own result. Returns 202. Returns 404 if there's no active lottery or the user didn't participate, and 429 `rate_limited`. |

Validation rules:

- `email`: an `EmailStr`.
- `password`: at least 6 characters (the Supabase default).
- `username`: 2–30 characters, trimmed, and unique case-insensitively.

## Steps

### 1. Supabase project setup (manual, in the dashboard)

1. Create a free project at supabase.com in an EU region.
2. **Authentication → Sign In / Providers → Email**: keep Email enabled, turn **"Allow new users to sign up" off** (sign-up goes only through the backend admin API), and turn **"Confirm email" off**.
3. In **SQL Editor**, run `supabase/migrations/0001_init.sql` (created in step 3).
4. Collect these values:
   - Project URL.
   - Publishable/anon key, for the frontend.
   - Secret/service-role key, for the backend.
   - The Session pooler connection string (**Connect → Session pooler**), for the backend.

### 2. Repository restructure

1. Create branch `refactor/python-backend` from `master`.
2. `git mv` the Nuxt files (`app.vue`, `nuxt.config.ts`, `layouts/`, `pages/`, `public/`, `package.json`, `yarn.lock`, `tsconfig.json`) into `frontend/`.
3. Delete `package-lock.json`, `server/`, `script/` and `assets/participants.json`.
4. Update `.gitignore` with `.venv/`, `__pycache__/`, `.pytest_cache/` and `.ruff_cache/`.

### 3. Database migration

1. Write `supabase/migrations/0001_init.sql` exactly as in the schema section above.
2. Run it in the Supabase SQL Editor.
3. Verify: inserting two rows with `is_master = true` into `profiles` fails, and a second `status='finished'` row in `lotteries` fails.

### 4. Backend skeleton

1. `cd backend && uv init --app && uv add fastapi "uvicorn[standard]" "psycopg[binary,pool]" pydantic-settings "pydantic[email]" supabase "pyjwt[crypto]" httpx`
2. `uv add --dev pytest pytest-asyncio ruff`
3. `app/config.py`: a `Settings` class (pydantic-settings) with:
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_ROLE_KEY`
   - `DATABASE_URL`
   - `BREVO_API_KEY`
   - `EMAIL_SENDER_ADDRESS`
   - `EMAIL_SENDER_NAME`
   - `CORS_ORIGINS` (a comma-separated list)
   - `MIN_PARTICIPANTS` (default 3)
   - `EMAIL_COOLDOWN_MINUTES` (default 10)
4. `app/db.py`: an `AsyncConnectionPool`, opened and closed in the FastAPI `lifespan`, plus a `get_conn` dependency.
5. `app/main.py`: the app with `CORSMiddleware` (`allow_origins=settings.CORS_ORIGINS` and the `Authorization` header), routers under `/api`, and `GET /api/health`.
6. `backend/.env.example` with every key above and empty values.
7. Verify: `uv run uvicorn app.main:app --reload` starts, and `GET /api/health` returns `{"status":"ok"}`.

### 5. Authentication in the backend

1. `app/auth.py`:
   - A `PyJWKClient(f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json")` with caching.
   - `get_current_user_id` decodes the bearer token with `audience="authenticated"` and the algorithms `["ES256","RS256"]`, and returns `sub`. If the token is missing or invalid it returns 401.
   - Fallback: if the project still uses a legacy HS256 secret, `SUPABASE_JWT_SECRET` is used instead.
2. `get_current_profile` loads the `profiles` row for that id and returns 401 if it doesn't exist.
3. `require_master` returns 403 `not_master` when `is_master` is false.
4. `app/supabase_admin.py`: `create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)`.
5. `routers/auth.py` → `POST /auth/register`:
   1. Pre-check that the username (case-insensitive) is free, and that the master slot is free if `is_master` is true. Return 409 otherwise.
   2. Call `auth.admin.create_user({email, password, email_confirm: True, user_metadata: {username}})`. If the email already exists, return 409 `email_taken`.
   3. In one transaction, insert the `profiles` row and a `lottery_logs` row (`user_registered`).
   4. If the insert fails with a unique violation, call `auth.admin.delete_user(id)` and return 409 with the matching `detail` (inspect the constraint name).
6. `GET /auth/master-available` checks whether a profile with `is_master` exists.
7. `routers/me.py` → `GET /me`.

### 6. Draw logic

1. `app/draw.py`: `draw(ids: list[UUID]) -> dict[UUID, UUID]`.
   - Use `secrets.SystemRandom().shuffle`, and repeat until no giver gets themselves (a port of the current `script/draw.js` algorithm).
   - Raise `ValueError` when `len(ids) < 2`. The `MIN_PARTICIPANTS` check lives in the router.
2. `tests/test_draw.py`:
   - Over 10,000 runs with 3–10 ids, every result is a bijection with no self-pair.
   - With 2 ids, the result is always the swap.
   - With fewer than 2 ids, it raises.

### 7. Lottery endpoints

1. `GET /lottery/current`:
   - Select the lottery with `status='finished'`. If there is none, return `{status:"not_started", …null}`.
   - Otherwise join `lottery_results` with `profiles` on `receiver_id` where `giver_id = me`.
   - `participated` is false when the user has no row (they registered after the draw).
2. `POST /lottery` (master), in one transaction:
   1. `select id from profiles order by created_at for update`.
   2. Return 400 if the count is below `MIN_PARTICIPANTS`.
   3. Insert into `lotteries` with `status 'finished'`, returning `id`. A unique violation on `lotteries_single_active` becomes 409 `lottery_active`.
   4. Insert the pairs with `executemany` into `lottery_results`.
   5. Insert a `lottery_logs` row (`lottery_started`, details `{"participants": N}`).
3. `DELETE /lottery/current` (master): update the active lottery to `cancelled` and set `cancelled_by` and `cancelled_at`, then write a log entry (`lottery_cancelled`).
4. `GET /participants` (master).
5. `POST /lottery/current/email`:
   1. Load the user's result. Return 404 if there's none.
   2. Rate limit: if a `result_email_sent` log for this actor and lottery exists from within the last `EMAIL_COOLDOWN_MINUTES`, return 429.
   3. Call `email.send_result(to=profile.email, username=profile.username, receiver=receiver_username)`.
   4. Write a log entry (`result_email_sent`). Return 202.

### 8. Email sender

1. `app/email.py`: `httpx.AsyncClient.post("https://api.brevo.com/v3/smtp/email")` with:
   - Header `api-key: BREVO_API_KEY`.
   - Sender `{name, email}` and recipient `[{email, name: username}]`.
   - Subject: `Wynik losowania prezentów`.
   - HTML body: `Cześć {username}! Wylosowałeś/aś {receiver}. Pomyśl o jakimś prezencie.`
2. If Brevo returns a non-2xx response, the endpoint returns 502 `email_failed` and writes no log entry.
3. Manual setup: create a free Brevo account, verify the sender address under **Senders**, and create an API key.

### 9. Backend tests and lint

1. `tests/test_api.py`: use FastAPI `TestClient`, override `get_current_profile` and `get_conn` with fakes, and stub `email.send_result`. Cover:
   - 403 on master endpoints for non-masters.
   - 400 when there are not enough participants.
   - 409 when a lottery is already active.
   - The `lottery/current` shape before and after a draw, and for a late user.
   - 429 on the email cooldown.
2. `uv run ruff check . && uv run ruff format --check . && uv run pytest`

### 10. Frontend rewrite

1. In `frontend/`:
   - `yarn remove @emailjs/browser rfdc`
   - `yarn add @supabase/supabase-js`
   - `yarn add -D typescript vue-tsc`
   - Upgrade `@nuxt/ui` to the latest 2.x.
2. `nuxt.config.ts`:
   - `ssr: false`
   - `modules: ['@nuxt/ui']`
   - `runtimeConfig.public = { supabaseUrl: '', supabaseAnonKey: '', apiBase: '' }`, set through `NUXT_PUBLIC_SUPABASE_URL`, `NUXT_PUBLIC_SUPABASE_ANON_KEY` and `NUXT_PUBLIC_API_BASE`.
   - Add `frontend/.env.example`.
3. `plugins/supabase.client.ts`: `createClient(url, anonKey)`, provided as `$supabase`.
4. `composables/useAuth.ts`:
   - A `session` state (`useState`), initialised from `getSession()`, with an `onAuthStateChange` listener.
   - `signIn(email, password)` returns a boolean.
   - `signOut()` and `accessToken()`.
5. `composables/useApi.ts`: `$fetch.create({ baseURL: apiBase, onRequest })`, which adds `Authorization: Bearer <token>`.
6. `middleware/auth.global.ts`:
   - Logged out on `/panel` → redirect to `/`.
   - Logged in on `/` or `/rejestracja` → redirect to `/panel`.
7. `layouts/default.vue`: keep the card with the header "Losowanie prezentów".
8. `pages/index.vue` (login):
   - `UFormGroup label="email:"` with `UInput type="email"`.
   - `UFormGroup label="hasło:"` with `UInput type="password"`.
   - A `UButton type="submit"` labelled "Zaloguj się".
   - A `UButton variant="outline" to="/rejestracja"` labelled "Zarejestruj się".
   - When `signIn` fails, show `<p class="text-red-500">Nieudane logowanie, wprowadź prawidłowy adres email i hasło</p>` under the inputs. It disappears on the next submit.
   - On success, `navigateTo('/panel')`.
9. `pages/rejestracja.vue`:
   - Fields: "email:", "hasło:", "nazwa użytkownika:".
   - `URadioGroup` with the legend "Czy jesteś mistrzem losowania?" and the options Tak/Nie (default Nie). Disable "Tak" with the hint "Mistrz losowania już istnieje" when `GET /auth/master-available` returns false.
   - Submit button "Zarejestruj się": `POST /auth/register`, then `signIn`, then `/panel`.
   - Error messages by `detail`:
     - `email_taken` → "Ten adres email jest już zarejestrowany"
     - `username_taken` → "Ta nazwa użytkownika jest już zajęta"
     - `master_taken` → "Mistrz losowania już istnieje"
     - 422 → "Sprawdź poprawność danych (hasło min. 6 znaków)"
   - Link "Masz już konto? Zaloguj się" → `/`.
10. `pages/panel.vue`: on mount, load `GET /me` and `GET /lottery/current` (plus `GET /participants` when the user is the master). Render in order:
    1. `Witaj {username}`.
    2. `UButton` "Uruchom losowanie": `:disabled="!me.is_master || lottery.status === 'finished'"`, behind a confirm modal. Then `POST /lottery` and reload the status.
    3. `UButton` "Kasuj wyniki losowania": `:disabled="!me.is_master || lottery.status !== 'finished'"`, behind a confirm modal. Then `DELETE /lottery/current` and reload.
    4. For the master only: "Uczestnicy (N): a, b, c".
    5. The status text:
       - `not_started` → "Twoje losowanie jeszcze się nie zaczęło".
       - `finished` and `participated` → "Oto wyniki Twojego losowania", then "Wylosowałeś/aś {receiver_username}. Pomyśl o jakimś prezencie.", then `UButton` "Wyślij wynik na swój adres mailowy". On a 202, show a toast "Wysłano wynik na {email}". On a 429, show "Spróbuj ponownie za kilka minut".
       - `finished` and not `participated` → "Losowanie odbyło się przed Twoją rejestracją. Poproś mistrza losowania o ponowne losowanie."
    6. `UButton` "Wyloguj się": `signOut()`, then `navigateTo('/')`. It's always visible.
    7. Backend errors are shown with `useToast()`. A 400 `not_enough_participants` shows "Za mało uczestników (min. 3)".
11. Delete `pages/login/`.
12. Verify: `npx nuxi typecheck` and `yarn build`.

### 11. Local end-to-end check

1. Start the backend: `cd backend && cp .env.example .env` (fill it in), then `uv run uvicorn app.main:app --reload --port 8000`.
2. Start the frontend: `cd frontend && cp .env.example .env` (with `NUXT_PUBLIC_API_BASE=http://localhost:8000/api`), then `yarn dev`.
3. Scenario:
   1. Register user A as master. Registering user B as master is rejected.
   2. Register B, C and D as non-masters.
   3. Log in with a wrong password and check that the error text appears.
   4. Log in as B: "Twoje losowanie jeszcze się nie zaczęło", both master buttons are disabled, and "Wyloguj się" works.
   5. Log in as A with only 2 users registered: "Uruchom losowanie" gives the "Za mało uczestników" toast.
   6. With 4 users: A starts the lottery, and every user sees a different receiver that isn't themselves.
   7. B sends the email, it arrives, and a second click within 10 minutes is rate limited.
   8. Register E: E sees the late-registration message.
   9. A clicks "Kasuj wyniki losowania": everyone sees "not started" again. In Supabase, `lotteries` shows the old id as `cancelled`, and `lottery_logs` contains every action with its `lottery_id`.

### 12. Deployment

1. Root `vercel.json` defines two Vercel Services (beta, all plans) in one project: `frontend` (root `frontend/`, Nuxt, `yarn generate`, output `.output/public`, SPA rewrite to `/index.html`) and `backend` (root `backend/`, FastAPI, entrypoint `app.main:app`). Top-level rewrites send `/api/(.*)` to `backend` and everything else to `frontend`. The backend receives the original path, so the `/api` prefix stays.
2. Vercel project: root directory = repository root. Env vars (shared): the `NUXT_PUBLIC_*` vars with `NUXT_PUBLIC_API_BASE=/api`, and the backend vars from `backend/.env.example` with `DATABASE_URL` set to the Supabase Transaction pooler (port 6543).
3. Same origin in production, so CORS only matters locally.
4. The backend runs on Fluid compute: the pool is small (`min_size=0`, `max_size=3`) and closes within the 500 ms shutdown window.
5. Known limits of the free tiers:
   - Vercel Hobby is for non-commercial use; functions have cold starts but don't sleep for a minute like Render free.
   - A Supabase free project pauses after 7 days without activity.

### 13. Documentation

1. Rewrite `CLAUDE.md`: the new structure, the commands for both apps, the env vars, the schema summary, and the deployment steps.
2. Replace `README.md` with a setup guide (Supabase, Brevo, local run, deploy).
3. Optional: `assets/participants.json` with real emails stays in git history. Rewrite the history (`git filter-repo --path assets/participants.json --invert-paths`) before making the repo public.
