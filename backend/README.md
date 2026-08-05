# Draftly backend

FastAPI modular monolith. Phase 2 (auth) is implemented. Phase 3 onward
builds on the ports and `RequestContext` this module provides.

## Quick start

```bash
# Install dependencies
uv sync

# Apply migrations to Neon (uses DATABASE_URL_DIRECT)
uv run alembic upgrade head

# Start the dev server
uv run uvicorn src.main:app --reload --port 8000
```

Health checks:

```
GET /health/live   → {"status": "ok"}
GET /health/ready  → {"status": "ok", "db": "ok"}
```

## Environment variables

Copy `backend/.env.example` to `backend/.env` and fill in your values.
Never commit secrets. The frontend has its own file:
`frontend/.env` (from `frontend/.env.example`).

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | ✅ | Pooled Neon URL (app runtime) |
| `DATABASE_URL_DIRECT` | ✅ | Direct Neon URL (Alembic migrations) |
| `CLERK_ISSUER` | After Clerk setup | Frontend API URL from Clerk dashboard |
| `CLERK_SECRET_KEY` | After Clerk setup | `sk_test_…` secret key |
| `USE_STUB_IDENTITY` | `true` locally | Skip Clerk JWT, use synthetic demo identity |

Clerk publishable key and `AUTH_BYPASS` live only in `frontend/.env`.

## Project structure

```
backend/
├── src/
│   ├── main.py            FastAPI factory, health routes, CORS
│   ├── bootstrap.py       Composition root — ports ↔ adapters
│   ├── api/deps.py        Shared FastAPI deps (get_request_context)
│   ├── platform/          Shared technical kernel
│   │   ├── config.py      pydantic-settings
│   │   ├── errors.py      DraftlyError hierarchy + ErrorEnvelope
│   │   ├── request_context.py  Immutable RequestContext
│   │   └── db/            SQLAlchemy async engine + UnitOfWork
│   └── modules/
│       ├── auth/          Identity, roles, memberships, capabilities
│       └── audit/         Append-only event log with hash chaining
├── migrations/            Alembic migration versions
├── tests/
│   ├── security/          Isolation and existence-hiding tests
│   └── contract/          /me response matches frontend User shape
└── pyproject.toml
```

## Running tests

```bash
uv run pytest -v
```

38 tests pass. All run without a live database — they use in-memory fakes.

## Architecture rules

1. Domain layer (`domain/`) must not import FastAPI, SQLAlchemy, or Clerk.
2. Application services (`application/`) depend on Ports (protocols), never
   on concrete adapters.
3. Wiring happens only in `bootstrap.py`.
4. Every authenticated route uses `Depends(get_request_context)`.
5. Non-member matter requests receive 404, never 403 (existence hiding).
6. Every material mutation writes an audit event in the same transaction.

## Clerk setup (external step)

1. Create an app at [dashboard.clerk.com](https://dashboard.clerk.com)
2. Enable Google OAuth + Email verification code
3. Enable **Restricted sign-up** (require invitations)
4. **Sessions → Multi-session handling OFF**; prefer single-session / revoke
   other sessions on sign-in if the dashboard offers it
5. Add `CLERK_ISSUER` and `CLERK_SECRET_KEY` to `backend/.env`, and
   `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` + `CLERK_SECRET_KEY` to
   `frontend/.env`
6. Set `USE_STUB_IDENTITY=false` in `backend/.env`
7. Allowed origins: `http://localhost:3000` and `http://localhost:4310`
