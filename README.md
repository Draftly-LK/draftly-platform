# draftly-platform

Legal workflow platform for Sri Lankan practice.

See [docs/plan.md](docs/plan.md) for the M2 static UI implementation plan.

- Backend design: [backend/backend-implementation-plan-v0.md](backend/backend-implementation-plan-v0.md)
  and the service catalogue in
  [backend/docs/services/README.md](backend/docs/services/README.md).
- Agent conventions: [CLAUDE.md](CLAUDE.md) (applies to every AI agent).
- Pull-request review pipeline: [docs/CODE_REVIEWER.md](docs/CODE_REVIEWER.md).

## Prerequisites

- Node.js `>=22.16.0 <23` and pnpm `>=10.23.0 <11` (pinned via Corepack)
- Python 3.12 and [uv](https://docs.astral.sh/uv/)

## Local development (Windows PowerShell)

Run the backend and frontend in two separate PowerShell terminals. There is no
repo-root `.env`; each application has its own environment file.

### First-time environment setup

From the repository root:

```powershell
Copy-Item backend\.env.example backend\.env
Copy-Item frontend\.env.example frontend\.env
```

Add valid `DATABASE_URL` and `DATABASE_URL_DIRECT` values to `backend/.env`.
For local development without Clerk authentication, also set:

```dotenv
# backend/.env
USE_STUB_IDENTITY=true

# frontend/.env
AUTH_BYPASS=true
```

Keep the frontend API URL set to the local backend:

```dotenv
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

## Frontend

In the frontend PowerShell terminal, from the repository root:

```powershell
corepack enable
pnpm --dir frontend install
pnpm --dir frontend dev --port 4310
```

On later runs, only the development-server command is needed. Alternatively,
run the commands from inside `frontend/`:

```powershell
cd frontend
pnpm install
pnpm dev --port 4310
```

App: [http://localhost:4310](http://localhost:4310)

### Auth (Clerk)

- Sign-in: `/sign-in` · Sign-up: `/sign-up` · Profile: `/profile` · Sign-out → `/sign-in`
- Configure keys in `frontend/.env` (see `frontend/.env.example`)
- `AUTH_BYPASS=true` skips login redirects while developing. Ignored when
  `NODE_ENV=production`. Use `false` for real sign-in testing and in deploy.
- To remove the bypass later: delete `frontend/src/lib/auth/bypass.ts`, drop
  its middleware / AppShell usages, and remove `AUTH_BYPASS` from
  `frontend/.env.example`.

### Interface language

- `MULTILINGUAL_LANGUAGE_SUPPORT` in `frontend/.env` controls the Sinhala UI
  locale. Default (unset or any value but `false`) keeps English + Sinhala.
- `MULTILINGUAL_LANGUAGE_SUPPORT=false` serves English only: the
  `draftly-locale` cookie is ignored and the locale toggle is not rendered.
- The flag gates interface chrome only. A matter's instrument language and a
  document's language stay part of the matter record either way.

#### Clerk Dashboard (required for one email + one session)

In [dashboard.clerk.com](https://dashboard.clerk.com) for this app:

1. **Sessions** → turn **Multi-session handling OFF** (one account in the browser).
2. If available, enable **single session / revoke other sessions on sign-in** so a
   new login ends the previous one.
3. Keep **restricted / invitation-only** sign-up; do not let end users add
   secondary emails.
4. Allowed origins for local work: `http://localhost:3000` and
   `http://localhost:4310` only.
5. Draftly UI does not expose “Add email” / linked-email management — profile
   email is read-only.

## Backend

In the backend PowerShell terminal, from the repository root:

```powershell
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn src.main:app --reload --port 8000
```

On later runs, start the backend with:

```powershell
cd backend
uv run uvicorn src.main:app --reload --port 8000
```

API: [http://localhost:8000](http://localhost:8000) —
`GET /health/live` and `GET /health/ready` for health checks.

More detail (env vars, tests, architecture): [backend/README.md](backend/README.md).
