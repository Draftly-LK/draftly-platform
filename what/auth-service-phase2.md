# Auth Service Implementation — Phase 2

**Completed:** 2026-08-04  
**Branch:** `dev/lahiru/auth`  
**Commits:** 9 (Phase 0 → Phase 2 + frontend profile)

---

## What was built

### Backend — 9 commits

| # | Commit | Key files |
|---|---|---|
| 1 | `feat(backend): initialise uv project and Phase 0 foundation` | `pyproject.toml`, `platform/config.py`, `platform/errors.py`, `platform/request_context.py`, `platform/db/session.py`, `platform/db/unit_of_work.py`, `platform/observability/logging.py`, `src/main.py`, `src/bootstrap.py` |
| 2 | `feat(auth): add domain models, enums, and capability policy map` | `domain/models.py` (OrgRole MVP: owner\|member), `domain/policies.py` (CAPABILITY_MAP), `domain/errors.py` |
| 3 | `feat(auth): add ORM models and Alembic migrations` | `infrastructure/orm.py`, `migrations/versions/auth_0001_*.py`, `migrations/versions/audit_0001_*.py` — **applied to Neon** |
| 4 | `feat(auth): implement ports, repositories, and Clerk identity adapter` | `ports.py`, `infrastructure/repository.py`, `infrastructure/clerk_adapter.py`, `infrastructure/stub_adapter.py` |
| 5 | `feat(auth): implement auth_service core methods` | `application/auth_service.py` — all 8 methods from spec |
| 6 | `feat(auth): add API router, schemas, and FastAPI deps` | `api/schemas.py`, `api/router.py`, `src/api/deps.py` |
| 7 | `feat(audit): add audit domain model, port, and insert-only repository` | `audit/domain/models.py`, `audit/ports.py`, `audit/application/audit_service.py`, `audit/infrastructure/repository.py` |
| 8 | `test(auth): add policy, service, security, and contract tests` | 38 tests, 38 pass |
| 9 | `feat(frontend): add Clerk profile image to sidebar` | `components/shell/user-button.tsx`, updated `sidebar.tsx` |

---

## Architecture decisions

- **OrgRole = owner | member** — `admin` deferred for MVP per user request
- **StubIdentityAdapter** — active when `USE_STUB_IDENTITY=true` or Clerk keys absent; never in production
- **ClerkIdentityAdapter** — JWKS-based JWT validation, no Clerk SDK, fully provider-neutral behind `IdentityPort`
- **404-not-403** — non-member matter requests return 404 to hide existence (security-model.md §5)
- **Admin lockout guard** — `set_user_role` blocks removing the last organisation owner
- **AuditPort in same transaction** — `assign_membership` and `set_user_role` write audit events inside the same DB tx as the mutation
- **Hash chaining** — each audit event stores `prevHash` + SHA-256 `hash`; retroactive edits break the chain

---

## Database tables created (Neon)

- `users` — account entity
- `user_identities` — (issuer, subject) → user_id link
- `organisations` — tenant boundary
- `organisation_memberships` — (org, user, role: owner|member)
- `matter_memberships` — (org, matter, user, role: assignee|supervisor)
- `invitations` — admin-issued, activates pending accounts
- `audit_events` — insert-only, org-scoped, hash-chained

---

## Tests (38 total, 38 pass)

| File | Coverage |
|---|---|
| `test_policies.py` | All capability grants and denials from security-model.md §3.2 |
| `test_auth_service.py` | authorize (404/403), membership audit, admin lockout |
| `test_auth_security.py` | Existence hiding, role isolation, privilege escalation |
| `test_me_contract.py` | GET /me response matches frontend `User` type (camelCase) |

---

## Frontend change

`components/shell/user-button.tsx`:
- **With Clerk** (`NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` set): renders `<UserButton>` from `@clerk/nextjs` — shows real profile photo, opens Clerk modal on click
- **Without Clerk** (demo/CI): renders initials avatar with role badge from demo store

`components/shell/sidebar.tsx`:
- `<UserButton>` placed at the top of the sidebar footer, above Settings / Help / Reset

---

## What you still need to do externally

1. **Create a Clerk application** at [dashboard.clerk.com](https://dashboard.clerk.com)
   - Enable Google OAuth, Email OTP, Restricted sign-up
2. **Add keys to `.env`**:
   ```
   CLERK_ISSUER=https://...
   CLERK_SECRET_KEY=sk_test_...
   NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...
   USE_STUB_IDENTITY=false
   ```
3. Run `uv run alembic upgrade head` (already done against current Neon)
4. Start the backend: `uv run uvicorn src.main:app --reload --port 8000`
