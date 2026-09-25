# Draftly — Production Deployment Plan

**Canonical deployment document for this repository.** Supersedes the earlier
hosting-architecture draft, which is absorbed here.

Audit date: 2026-09-14. Method: `devops-engineer` discipline (build / deploy /
ops) applied to a full read of `backend/`, `frontend/`, `landing-page/`,
`.github/workflows/`, `backend/contracts/`, and `backend/docs/`.

Companion documents:

- `docs/TESTING_PLAN.md` — the canonical test plan. §9 below states which of its
  suites gate a deploy; it does not restate them.
- `backend/docs/infrastructure.md` — the authoritative provider decisions,
  environment matrix, and PDPA gates. Where this document and that one disagree,
  that one wins.
- `backend/docs/service-definition-of-done.md` — the L0–L4 readiness rubric this
  plan's verdict is measured against.
- `backend/docs/jobs-and-workers.md` — the intended worker and scheduler runtime.

Status vocabulary used throughout: **Ready** (exists and works),
**Partial** (exists, incomplete or unverified), **Missing** (does not exist),
**Blocked** (cannot proceed until a named decision or approval lands).

---

## 0. Verdict

**The application is not production-ready.** It is ready for a staging
deployment on synthetic data, which is exactly what the repo's own documents say
it should be doing at this phase.

Two independent lines of evidence agree.

**By the repo's own rubric.** `backend/docs/service-definition-of-done.md` §1
defines five levels, L0 designed through L4 accepted. `backend/contracts/services.yaml`
records four services at **L3** (`billing_service`, `party_service`,
`obligations_service`, `notarial_register_service`, plus `notification_service`)
and the remaining twenty at **L0**. **No service has reached L4.** L2 —
"the cross-service conformance suite passes for this service" — cannot currently
be reached by any service at all, because `backend/tests/conformance/` contains
only a `.gitkeep`, and because `backend/docs/security-model.md` §2.1 declares the
tenancy-key question "**open … Blocks L2 for every service**".

**By deployment artifacts.** There are none. No `Dockerfile`, no
`compose.yml`, no `.dockerignore`, no systemd unit, no image registry, no
migration runner, no seed script, no smoke test, no rollback procedure. The
previous version of this document described a Docker Compose topology in the
present tense; that was a proposal, and this version says so.

### The eighteen requested areas

| # | Area | Status | One-line evidence |
|---|---|---|---|
| 1 | Architecture and components | **Partial** | Components exist; the scheduler runtime named in `backend/docs/jobs-and-workers.md` §1 does not |
| 2 | Deployment order | **Partial** | Order is sound and documented below; no runner exists to execute the migration step |
| 3 | Dev / staging / production environments | **Partial** | Five environments in `backend/docs/infrastructure.md`; `ENVIRONMENT=staging` matches neither guard in `backend/src/platform/config.py` |
| 4 | Environment variables and secrets | **Partial** | 19 `Settings` fields absent from `backend/.env.example`; `use_stub_billing` defaults `True`; no secret manager |
| 5 | Infrastructure and external services | **Blocked** | Every real-data provider gate is closed by design pending PDPA sign-off |
| 6 | Build and release | **Missing** | No Dockerfile, no unit files, no registry, no version tagging |
| 7 | Migrations and rollback | **Partial** | 20 additive revisions, single head; downgrade path never executed |
| 8 | CI/CD with quality gates | **Partial** | `.github/workflows/ci.yml` skips 43 of 66 backend test files and all frontend tests |
| 9 | Tests before deployment | **Partial** | See `docs/TESTING_PLAN.md` §0 — four Critical findings open |
| 10 | Health checks and smoke tests | **Partial** | `/health/live` and `/health/ready` are correct; no smoke test exists |
| 11 | Logging, monitoring, tracing, alerts | **Missing** | Structured logs only; zero metrics, zero tracing, zero alerts |
| 12 | Backup and disaster recovery | **Missing** | Neon PITR assumed; `backend/docs/infrastructure.md`: "A restore that has never been executed is not a backup" |
| 13 | Security checks and access controls | **Partial** | Strong in-code authz; no rate limiting, no security headers, no image scanning |
| 14 | Zero-downtime strategy | **Partial** | Rolling deploy is viable; VPS-1 is a single point of failure by design |
| 15 | Rollback triggers and procedure | **Missing** | Nothing to roll back to without tagged images |
| 16 | Post-deployment verification | **Partial** | Runbook §2.3 step 9 exists; no formal checklist until §16 below |
| 17 | Risks, blockers, assumptions | **Ready** | §17 |
| 18 | Sequence and owners | **Partial** | Sequence in §18; owners unassigned in the repo |

### Blockers, in the order they must clear

| # | Blocker | Owner | Gates |
|---|---|---|---|
| B1 | PDPA 2022: data residency, processor agreements, lawyer sign-off for Neon, GCS, Gemini, Cloud Vision, Resend, PayHere | Legal + Ops | Any real client data. `backend/docs/infrastructure.md` |
| B2 | Tenancy-key decision — `user_id` (code) vs `organisation_id` (`backend/docs/events.md` §2, DoD §4.1.5) | Platform team | L2 for every service. Self-declared blocking in `backend/docs/security-model.md` §2.1 |
| B3 | No build artifacts — Dockerfile, units, registry | Engineering | Any repeatable deploy. §6 |
| B4 | No scheduler runtime; nine scheduled jobs have no executor | Engineering | Reminders, retention, export expiry, orphan collection. §1.3 |
| B5 | No backup restore has ever been executed; RPO/RTO unconfirmed | Ops + practice | Holding real data. §12 |
| B6 | `landing-page/` is a mirror of a third-party site and must not be deployed | Product | Public launch. §17.3 |
| B7 | Four Critical test findings open, incl. no test of the real auth path | Engineering | `docs/TESTING_PLAN.md` §0 F1–F4 |

---

## 1. System architecture and deployable components

### 1.1 What has to run

| Process | Command | Port | Stateless? | Status |
|---|---|---|---|---|
| Frontend | `pnpm start` (Next.js) | 3000 | Yes | **Partial** — `output: "standalone"` is not set (§6.2) |
| API | `uvicorn src.main:app --host 0.0.0.0 --port 8000` | 8000 | Yes | **Ready** |
| Worker | `python -m src.workers.runner` | — | Yes | **Ready** — `backend/src/workers/runner.py` |
| Scheduler | `python -m src.workers.runner --sched` | — | Leader-only | **Missing** — the flag does not exist (§1.3) |
| Migrations | `alembic upgrade head` against `DATABASE_URL_DIRECT` | — | Once per release | **Partial** — no runner script |

The app tier is genuinely stateless. No state touches local disk when
`SOURCE_FILE_STORAGE=object_storage`; sessions are a Clerk JWT in a cookie, so
no sticky sessions are needed; the job queue is a Postgres table. That is what
makes load balancing and rolling deploys straightforward here, and it is
enforced in code — `backend/src/bootstrap.py` refuses `filesystem` storage
outside `{local, test, ci}` precisely so a second VM cannot silently fail to
read a file the first one wrote.

Deployable components, complete list:

1. `backend/` — FastAPI app, worker, Alembic migrations. One image serves all
   three roles; only the command differs.
2. `frontend/` — Next.js 15 App Router. `frontend/vercel.json` is
   `{"git": {"deploymentEnabled": false}}` — a kill switch that stops Vercel
   auto-deploying, not a competing deployment target. It is inert against the
   topology below.
3. `landing-page/` — **not deployable.** See §17.3.

### 1.2 Topology

VPS-1 is the edge. VPS-2 is capacity. They link over the Google private VPC on
internal IPs, never the public internet.

```text
                          ┌─────────────────┐
                          │    Internet     │
                          └────────┬────────┘
                                   │  DNS → 34.x.x.x · HTTPS :443
╔══════════════════════════════════▼═══════════════════════════════════════╗
║  GOOGLE CLOUD VPC  "draftly-vpc"  ·  region asia-south1                  ║
║  ┌────────────────────────────────────────────────────────────────────┐  ║
║  │  VPS-1  draftly-edge   zone asia-south1-a                          │  ║
║  │  public 34.x.x.x (static) · internal 10.128.0.2                    │  ║
║  │   ┌──────────────────────────────────────────────────────────┐     │  ║
║  │   │  NGINX :443 — TLS termination + LOAD BALANCER            │     │  ║
║  │   │   /api/, /health/ ──▶ draftly_api  (least_conn)          │     │  ║
║  │   │        ├── 127.0.0.1:8000                                │     │  ║
║  │   │        └── 10.128.0.3:8000  ─────────────────────────────┼──┐  │  ║
║  │   │   /              ──▶ draftly_web  (least_conn)           │  │  │  ║
║  │   │        ├── 127.0.0.1:3000                                │  │  │  ║
║  │   │        └── 10.128.0.3:3000  ─────────────────────────────┼──┤  │  ║
║  │   └──────────────────────────────────────────────────────────┘  │  │  ║
║  │   ┌──────────────────────▼───────────────────────────────────┐  │  │  ║
║  │   │  web  Next.js :3000  ·  api  uvicorn ×3 :8000            │  │  │  ║
║  │   │  scheduler (standby — NOT IMPLEMENTED, see §1.3)         │  │  │  ║
║  │   └──────────────────────────────────────────────────────────┘  │  │  ║
║  └────────────────────────────────────────────────────────────────┼──┼──╝
║     private VPC · 10.128.0.0/20 · plain HTTP · free ──────────────┘  │
║     firewall: tcp 3000,8000 from 10.128.0.0/20 ONLY ─────────────────┘
║  ┌────────────────────────────────▼───────────────────────────────────┐  ║
║  │  VPS-2  draftly-app    zone asia-south1-c   ·   NO public IP       │  ║
║  │   nginx :80 (thin local fan-out, no TLS)                           │  ║
║  │   web :3000 · api ×3 :8000 · worker (drains outbox) · scheduler    │  ║
║  └────────────────────────────────────────────────────────────────────┘  ║
║                          ┌────────▼────────┐                             ║
║                          │ Cloud NAT +     │ outbound only — lets VPS-2  ║
║                          │ Cloud Router    │ reach the internet          ║
╚═══════════════════════════════════│══════════════════════════════════════╝
        ┌───────────────┬───────────┴────────┬──────────────────┐
        ▼               ▼                    ▼                  ▼
  ┌───────────┐   ┌───────────┐      ┌──────────────┐   ┌─────────────┐
  │   Neon    │   │   Clerk   │      │  GCS bucket  │   │  Gemini +   │
  │ pooled +  │   │  (JWT)    │      │  (evidence)  │   │ Cloud Vision│
  │  direct   │   │           │      │              │   │             │
  └───────────┘   └───────────┘      └──────────────┘   └─────────────┘
      ▲                                     ▲
      └── BOTH VMs connect ─────────────────┘
          shared state lives here, never on a VM's disk
```

Request path: browser → TLS terminates at nginx on VPS-1 → path match
(`/api/*` and `/health/*` to the API pool, everything else to the web pool) →
`least_conn` picks local loopback or `10.128.0.3` → if VPS-2, plain HTTP over
the internal NIC, no TLS, no egress charge → VPS-2's nginx hands to its own
process on loopback → the app reads and writes Neon, GCS, Clerk, Gemini, all
external and shared. VPS-2 reaches them through Cloud NAT.

`least_conn`, not round-robin: Draftly mixes 50 ms list reads with 20 s
extraction calls, and round-robin keeps handing work to a VM already stuck on a
long request.

### 1.3 The scheduler gap — B4

`backend/docs/jobs-and-workers.md` §1 specifies three processes and is explicit
about the third:

> `scheduler  python -m workers.runner --sched   one leader, fires timed jobs`
>
> "It elects a leader through a **Postgres advisory lock** so running two
> replicas is safe; the loser idles."

`backend/docs/infrastructure.md` repeats it independently: "One runner process
plus a leader-elected scheduler."

**Neither exists.** `backend/src/workers/runner.py` has no `--sched` flag, and a
repo-wide search for `pg_advisory` across `backend/src/` and
`backend/migrations/` returns nothing. What does exist is `run_forever()`, which
loops `run_once()` at `DEFAULT_POLL_SECONDS = 1.0`, and `run_once()` calls
`reap_leases()` then `claim_batch()`. So two of the eleven scheduled jobs in
`backend/docs/jobs-and-workers.md` §6 are covered incidentally — `outbox.drain`
(every 5 s) and `lease.reap` (every 30 s) are effectively the worker loop.

The other nine have **no runtime at all**:

| Schedule | Job | Consequence of it never running |
|---|---|---|
| every 15m | `obligation.emit-reminders` | No deadline reminder is ever sent |
| hourly | `billing.reconcile-subscriptions` | Provider and local subscription state drift; no handler is even registered |
| hourly | `export.expire` | Export links never expire |
| hourly | `agent.purge-stream-events` | Stream events accumulate without bound |
| daily 02:00 | `storage.collect-orphans` | Orphaned blobs accumulate and are billed for |
| daily 02:30 | `retention.evaluate` | No retention disposition ever runs |
| daily 03:00 | `memory.compact` | — (memory service is L0) |
| daily 03:15 | `memory.reconcile-scopes` | — |
| monthly 1st 00:15 | `register.close-month` | The notarial monthly return never closes |

Two of those — retention evaluation and the monthly register close — are
legally significant, not merely operational.

**A second, subtler defect.** `backend/src/workers/runner.py` hardcodes
`DEFAULT_LEASE_SECONDS = 120` and passes it to `reap_leases()` for every message
type. `backend/docs/jobs-and-workers.md` §5 assigns per-type leases: 900 s for
`document.process` and `document.rebuild-derivatives`, 600 s for `export.render`
and `report.render`, 3600 s for `corpus.rebuild-index`, 300 s for
`research.compose-answer`. The outbox schema carries no per-row lease column.

So a `document.process` job that legitimately takes four minutes has its lease
reaped at two minutes and is re-claimed by another worker **while the first
worker is still running it**. Gemini and Cloud Vision are then called twice and
billed twice, and the second run's writes race the first's. The saving grace
today is that document processing runs synchronously in the HTTP request
(`SynchronousProcessingJob`) rather than through the worker — but that is a
current-phase choice, and the moment it moves to the queue this becomes a
duplicate-spend and data-race bug. Fix the lease before moving processing to the
worker, not after.

### 1.4 Shared state

| State | Where it lives | Why not on a VM |
|---|---|---|
| Matters, facts, issues, audit | Neon Postgres | Both VMs must see the same rows |
| Uploaded evidence | GCS | VPS-1 writing a file VPS-2 cannot read is silent data loss |
| Sessions | Clerk JWT in a cookie | Nothing server-side to share → no sticky sessions |
| Job queue | `outbox` table | `FOR UPDATE SKIP LOCKED` makes multiple workers safe |

`SELECT … FOR UPDATE SKIP LOCKED` engages only when
`session.bind.dialect.name == "postgresql"`. On SQLite the claim is unlocked —
relevant to tests, not to production, but it means the SQLite integration suite
proves nothing about concurrent claiming (`docs/TESTING_PLAN.md` §6.2).

---

## 2. Deployment order

Order matters because the schema must lead the code by exactly one step, and
because the LB must never route to a VM that is mid-restart.

```text
1. Build + push both images, tagged with the git SHA        (§6)
2. Run migrations ONCE, from one place, against DATABASE_URL_DIRECT  (§7)
3. Roll VPS-2:  pull → up -d → wait for /health/ready       (§10)
4. Confirm nginx on VPS-1 is serving from VPS-2 again       (§16)
5. Roll VPS-1:  same
6. Post-deployment verification                             (§16)
```

Why this order:

- **Migrations before either roll.** During steps 3–5 VPS-1 runs old code
  against the new schema. That is only safe if migrations are
  backward-compatible for one release — see §7.2.
- **VPS-2 before VPS-1.** VPS-2 carries no public IP, so if the new image is
  broken the blast radius is one backend in the pool and nginx's
  `proxy_next_upstream` routes around it. Rolling the edge first would expose
  the fault to every user.
- **One VM at a time, gated on `/health/ready`.** Both at once is a full outage.

**Status: Partial.** The order is correct and the health gate exists. What is
missing is anything to execute it: no image to pull, no compose file, no
migration runner, no deploy script. Today every step is a human typing commands
over SSH, which is the definition of a non-repeatable deploy.

---

## 3. Environments

`backend/docs/infrastructure.md` defines five. Reproduced with current status:

| Environment | Database | Object store | Providers | Data | Status |
|---|---|---|---|---|---|
| Local | Neon branch or container | Filesystem | Console + fake adapters | Synthetic | **Ready** |
| CI | Neon branch per PR, dropped after | Temp filesystem | Fakes; recorded fixtures | Synthetic | **Missing** — CI has no database at all (§8) |
| Preview | Neon branch per deployment | Private GCS preview bucket | Sandbox keys, allowlisted recipients | Synthetic | **Missing** — no preview pipeline |
| Staging | Neon | Private GCS staging bucket | Real providers, restricted allowlist | Synthetic + approved pilot | **Partial** — see the defect below |
| Production | Approved Postgres deployment | Approved GCS or self-hosted MinIO | Real providers | Real, after the B1 gates | **Blocked** |

> "**No production credential, address, or dataset appears in local, CI,
> preview, or demo environments.**" — `backend/docs/infrastructure.md`

### 3.1 Defect: `staging` falls through both guards

`backend/src/platform/config.py`:

```python
@property
def is_production(self) -> bool:
    return self.environment == "production"

@property
def is_non_production(self) -> bool:
    return self.environment in {"local", "test", "ci", "preview", "demo"}
```

`staging` is in neither set, yet `backend/.env.example` documents it as a valid
value (`# one of: local | ci | preview | staging | production`). Consequences on
a staging box:

- `backend/src/main.py` sets `docs_url=... if not settings.is_production else None`,
  so **`/docs` and `/redoc` are publicly exposed on staging**;
- every `is_non_production` guard treats staging as production-like;
- `configure_logging("DEBUG" if settings.environment == "local" else "INFO")`
  gives staging INFO, which is correct but incidental.

Note also `test` appears in `is_non_production` but not in the `.env.example`
list, and `demo` appears in neither list but is used in code. The set of valid
environment names is not defined in one place.

**Fix before any staging deploy:** add a `Literal` type or a validator on
`Settings.environment` so an unknown value fails boot rather than falling
through, and decide explicitly which side of each guard `staging` sits on.

---

## 4. Environment variables and secrets

`backend/src/platform/config.py` is authoritative. `backend/.env.example` is
documentation and is **incomplete** — see §4.3.

### 4.1 CORS — the one that breaks a split-domain deploy

`backend/src/main.py`:

```python
# In production, set ALLOWED_ORIGINS to the frontend domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:4310"],
    allow_credentials=True,
    allow_methods=["*"],
    expose_headers=["ETag", "X-Correlation-Id"],
)
```

`ALLOWED_ORIGINS` **does not exist.** A repo-wide search finds exactly one
occurrence: the comment above. There is no `Settings` field and no reader.

In the §1.2 topology this is survivable, because nginx serves the app and the
API from the same origin and same-origin requests send no `Origin` header
requiring a match. It breaks the moment anything is split across domains — a
preview deployment, a separate API subdomain, a mobile client. Because
`allow_credentials=True` is paired with an explicit list rather than a wildcard,
the failure mode is a hard refusal, not a security hole.

**Action:** add `cors_allowed_origins: str` to `Settings`, parse
comma-separated, default to the empty tuple in production and fail boot if
`is_production` and the list is empty.

### 4.2 Clerk — fails closed on a stale value

| Variable | Default | Production requirement |
|---|---|---|
| `CLERK_ISSUER` | `""` | The Clerk Frontend API URL |
| `CLERK_SECRET_KEY` | `""` | `sk_live_…` |
| `CLERK_AUDIENCE` | `""` | Blank accepts any audience — set to the app domain |
| `CLERK_AUTHORIZED_PARTY` | `""` | **Must be the public origin.** Comma-separated |
| `CLERK_LEEWAY_SECONDS` | `30` | Applied to `iat`, `nbf`, and `exp` |

`ClerkIdentityAdapter` checks the JWT `azp` against `clerk_authorized_parties`
and fails closed. A stale `localhost` value is a 401 on every authenticated
request, with no other symptom. Nothing tests this path
(`docs/TESTING_PLAN.md` F1), so the first signal will be a user report.

`CLERK_LEEWAY_SECONDS=30` only helps if the clock is roughly right. Enable
`systemd-timesyncd` on both VMs or every JWT reads as not-yet-valid.

### 4.3 Nineteen settings exist in code and are documented nowhere

Present on `Settings`, absent from `backend/.env.example`:

`EXTRACTION_SEND_ALL`, `PARTY_IDENTIFIER_KEY`, `PARTY_BLIND_INDEX_KEY`,
`USE_STUB_BILLING`, `PAYHERE_MERCHANT_SECRET`, `PAYHERE_CHECKOUT_BASE_URL`,
`BILLING_GRACE_PERIOD_DAYS`, `BILLING_WEBHOOK_MAX_BODY_BYTES`,
`PLATFORM_ADMIN_USER_IDS`, `API_CURSOR_SIGNING_KEY`, `RESEND_API_KEY`,
`RESEND_FROM_EMAIL`, `RESEND_WEBHOOK_SECRET`, `RESEND_OUTBOUND_ENABLED`,
`RESEND_ALLOWED_RECIPIENT_DOMAINS`, `NOTIFICATION_COMPLIANCE_ALLOWLIST`,
`NOTIFICATION_REQUIRE_PUBLISHED_TEMPLATE`, `EMAIL_SENDING_ENABLED`,
`RESEND_RECIPIENT_ALLOWLIST`, `COMPLIANCE_ALERT_USER_IDS`.

Three of those are actively dangerous:

- **`use_stub_billing` defaults to `True`.** An operator following
  `.env.example` to the letter ships a production box where every payment is
  stubbed, and nothing tells them.
- **`api_cursor_signing_key` defaults to `""`.** This is the HMAC key for
  pagination cursors. Nobody is told to set it, and no test covers forgery
  (`docs/TESTING_PLAN.md` F4).
- **`party_identifier_key` and `party_blind_index_key` default to `""`.** These
  are the field-encryption keys for NIC and passport values.
  `backend/docs/infrastructure.md` calls the party identity key "separate and
  rotatable", and rotation "re-wraps rather than re-encrypts in place" — none of
  which is discoverable from the example file.

Going the other way, two variables in `.env.example` have no `Settings` field
and are silently swallowed by `extra="ignore"`: `GOOGLE_APPLICATION_CREDENTIALS`
(harmless — the Google client libraries read it from the process environment
directly) and `USE_MOCK_PIPELINE` (genuinely dead; setting it does nothing).

**Action:** regenerate `backend/.env.example` from `Settings` and add a contract
test asserting the two stay in sync. This is the same pattern
`test_openapi_contract.py` already uses successfully.

### 4.4 The residency assertion that silently does not run

`.env.example` ships `DRAFTLY_GCS_LOCATION=asia-southeast1`, but
`Settings.gcs_location` defaults to `""`, and `_assert_bucket_policy` in
`backend/src/bootstrap.py` guards the region check with `if expected and …`.
An unset variable therefore **disables the data-residency assertion entirely**,
turning a documented approval control into a no-op.

Note also three different regions in play: `DRAFTLY_GCS_LOCATION=asia-southeast1`
(Singapore), `GCP_LOCATION=asia-south1` (Mumbai, for Gemini/Vertex), and the VPC
region `asia-south1`. That is deliberate but easy to trip over.

**Action:** make `gcs_location` required when `source_file_storage == "gcs"`.

### 4.5 The five gate flags

All default `false`, all fail closed. This is the best-designed part of the
configuration surface and should not be weakened.

| Flag | Refuses what | Opening it requires |
|---|---|---|
| `DRAFTLY_STORAGE_REAL_DATA_APPROVED` | GCS at startup, and every upload | B1 residency + processor + lawyer sign-off |
| `PROVIDER_DATA_APPROVAL` | Non-synthetic documents to Gemini / Document AI; routes them to manual review | B1 |
| `MATTER_AGENT_ENABLED` | Every agent route | Product decision |
| `SUPERMEMORY_ENABLED` | Semantic recall; Neon stays authoritative | B1 |
| `SUPERMEMORY_REAL_DATA_APPROVED` | External data transfer | B1 |

`backend/docs/infrastructure.md` lists `provider_data_approval` **being enabled**
as itself an alert condition. Preserve that.

Equivalent boot-time environment guards, all in `backend/src/bootstrap.py` and
covered by 19 tests in `backend/tests/unit/test_bootstrap_*.py`:
`USE_STUB_IDENTITY`, `EXTRACTION_PROVIDER=stub`, and
`SOURCE_FILE_STORAGE=filesystem` each raise a named `RuntimeError` outside
`{local, test, ci}`.

### 4.6 Secret handling

**Status: Missing.** There is no secret manager integration anywhere.

Current state: `backend/.env` (2.3 KB of real secrets) sits in the backend
directory. It is correctly gitignored (`.env*` with `!.env.example`), but any
deploy step that copies the backend tree wholesale ships a developer's
credentials to the VM.

Minimum acceptable: env files at `/etc/draftly/*.env`, mode `0600`, owner
`root`, never inside the image and never inside the repo tree.

Better, and what `backend/docs/infrastructure.md` implies: **GCP Secret
Manager** plus a startup script that materialises them, so a rebuilt VM picks up
secrets without anyone copying a file over SSH. The credentials model for GCS is
already Application Default Credentials only — "a service-account key belongs in
neither `.env` nor Neon" — so the machine identity pattern is established and
Secret Manager fits it.

Secret inventory to provision: both database URLs, Clerk issuer + secret key,
Gemini API key, GCS bucket/project (not secret) and the workload identity,
Resend API key + webhook secret, PayHere merchant secret + webhook secret,
`party_identifier_key`, `party_blind_index_key`, `api_cursor_signing_key`.

**IAM gotcha worth pinning here**, from `backend/docs/infrastructure.md`:
startup calls `get_bucket`, which needs `storage.buckets.get`.
`roles/storage.objectAdmin` does **not** grant it — the runtime identity also
needs `roles/storage.legacyBucketReader` or an equivalent custom role, or the
application refuses to start with a 403.

---

## 5. Infrastructure and external-service dependencies

### 5.1 Machine layout

| | **VPS-1 `draftly-edge`** | **VPS-2 `draftly-app`** |
|---|---|---|
| Machine type | `e2-standard-2` (2 vCPU / 8 GB) | `e2-standard-2` |
| Zone | `asia-south1-a` | `asia-south1-c` |
| Disk | 50 GB pd-balanced | 50 GB pd-balanced |
| OS | Ubuntu 24.04 LTS | Ubuntu 24.04 LTS |
| Public IP | **static, reserved** | **none** |
| Internal IP | 10.128.0.2 (reserved) | 10.128.0.3 (reserved) |
| Nginx role | TLS + load balancer | local fan-out only |
| Runs | web, api ×3, scheduler (standby) | web, api ×3, **worker**, scheduler |

**Reserve both internal IPs.** The nginx upstream block hardcodes `10.128.0.3`;
if VPS-2 reboots into a different DHCP address the LB silently 502s. Reserve it,
or use the internal DNS name
`draftly-app.asia-south1-c.c.PROJECT.internal`.

**Different zones, same region.** Different zones survive a zone outage; same
region keeps the internal hop at ~0.3 ms and free. `asia-south1` (Mumbai) is the
nearest region to Sri Lanka, roughly 40 ms RTT versus ~200 ms from a US region —
this single choice moves p95 more than any application tuning will.

### 5.2 Nginx on VPS-1

`/etc/nginx/sites-available/draftly`, VPS-1 only:

```nginx
upstream draftly_api {
  least_conn;
  server 127.0.0.1:8000    max_fails=3 fail_timeout=15s;
  server 10.128.0.3:8000   max_fails=3 fail_timeout=15s;
  keepalive 32;
}

upstream draftly_web {
  least_conn;
  server 127.0.0.1:3000    max_fails=3 fail_timeout=15s;
  server 10.128.0.3:3000   max_fails=3 fail_timeout=15s;
  keepalive 32;
}

server {
  listen 80;
  server_name draftly.example.lk;
  location /.well-known/acme-challenge/ { root /var/www/certbot; }
  location / { return 301 https://$host$request_uri; }
}

server {
  listen 443 ssl http2;
  server_name draftly.example.lk;

  ssl_certificate     /etc/letsencrypt/live/draftly.example.lk/fullchain.pem;
  ssl_certificate_key /etc/letsencrypt/live/draftly.example.lk/privkey.pem;

  # Must equal MAX_SOURCE_FILE_BYTES (52428800). If nginx is smaller, it 413s
  # before FastAPI can return its error envelope. See §13.4.
  client_max_body_size 50m;

  # The app sets NO security headers — next.config.ts has no headers().
  # These are the only ones the deployment gets. See §13.3.
  add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
  add_header X-Content-Type-Options "nosniff" always;
  add_header X-Frame-Options "DENY" always;
  add_header Referrer-Policy "strict-origin-when-cross-origin" always;

  location /health/ {
    proxy_pass http://draftly_api;
    access_log off;
  }

  location /api/ {
    proxy_pass http://draftly_api;
    proxy_http_version 1.1;
    proxy_set_header Connection "";
    proxy_set_header Host              $host;
    proxy_set_header X-Real-IP         $remote_addr;
    proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto https;
    proxy_read_timeout 120s;          # document processing is synchronous
    proxy_next_upstream error timeout http_502 http_503;
  }

  location / {
    proxy_pass http://draftly_web;
    proxy_http_version 1.1;
    proxy_set_header Connection "";
    proxy_set_header Host              $host;
    proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto https;
  }
}
```

`proxy_read_timeout 120s` is load-bearing: document processing runs
synchronously inside the request (`SynchronousProcessingJob`), so the default
60 s cuts extraction off mid-flight. If processing moves to the worker, this can
drop back — and §1.3's lease bug must be fixed first.

VPS-2 gets a much smaller file: `listen 80`, the same `client_max_body_size`,
`/api/` → `127.0.0.1:8000` and `/` → `127.0.0.1:3000`, no TLS, no upstream pool.

### 5.3 Firewall and access

| Rule | Direction | Source | Target | Ports |
|---|---|---|---|---|
| `allow-https-public` | ingress | `0.0.0.0/0` | tag `draftly-edge` | tcp:80,443 |
| `allow-internal-app` | ingress | `10.128.0.0/20` | tag `draftly-app` | tcp:80,3000,8000 |
| `allow-ssh-iap` | ingress | `35.235.240.0/20` | both tags | tcp:22 |
| *(implicit deny)* | ingress | everything else | — | — |

The second rule is the entire security story of the private link: VPS-2's app
ports are reachable from inside the VPC and nowhere else. Combined with no
public IP, there is no path from the internet to VPS-2. Ports 8000 and 3000 are
never internet-facing on either machine.

SSH through IAP TCP forwarding, never a public port 22:

```bash
gcloud compute ssh draftly-app --zone asia-south1-c --tunnel-through-iap
```

### 5.4 Cloud NAT

VPS-2 has no public IP but must reach Neon, Clerk, Gemini and GCS. Cloud NAT
gives it outbound-only internet.

```bash
gcloud compute routers create draftly-router \
  --network draftly-vpc --region asia-south1

gcloud compute routers nats create draftly-nat \
  --router draftly-router --region asia-south1 \
  --nat-all-subnet-ip-ranges --auto-allocate-nat-external-ips
```

Forgetting this is the most common way this topology fails on first boot: VPS-2
comes up, every process crashes on a database timeout, and the cause is not
obvious from the logs.

### 5.5 External services

Every one has a gate, per `backend/docs/infrastructure.md`. None of the gates
has cleared — that is B1.

| Service | Port | Status | Gate before real data |
|---|---|---|---|
| Neon Postgres | `DocumentRepository` et al. | **Partial** | Residency, processor agreement, lawyer sign-off (PDPA 2022) |
| Clerk | `IdentityPort` | **Partial** | Environment and role mapping approved |
| Google Cloud Storage | `ObjectStoragePort` | **Blocked** | Region, processor terms, access, encryption, retention, deletion, recovery, cost, lawyer approval — all recorded |
| Google Cloud Vision | `OcrPort` | **Blocked** | Same gate |
| Gemini | `ClassifierPort`, `ExtractorPort` | **Blocked** | Region, retention, training-use, quota, cost, exit — recorded and approved |
| Resend | `EmailPort` | **Missing** | Domain verified with SPF, DKIM, DMARC; processor terms reviewed |
| PayHere | `BillingProviderPort` | **Missing** | Onboarding, settlement, prices, refunds, retention. `use_stub_billing` defaults `True` |
| Screening | `ScreeningPort` | **Partial** | Manual-entry adapter in V0 |

Two connection strings are mandatory and distinct:

- `DATABASE_URL` — the **pooled** Neon endpoint (PgBouncer), used by the app.
- `DATABASE_URL_DIRECT` — the **direct, unpooled** endpoint, used by Alembic.
  `backend/docs/infrastructure.md`: "migrations misbehave through a transaction
  pooler."

Both require `sslmode=require` and `channel_binding=require`.

**Note on the V1 direction.** `backend/docs/infrastructure.md` states that for
V1 the database moves to "PostgreSQL on the team's own local or on-premises
servers", and that the migration is "a `pg_dump` and restore plus a connection
string change; no application code changes because the access layer is already
provider-neutral." That is a one-paragraph intention with no ops plan, no HA
design, and no runbook. Treat it as a direction, not a plan.

---

## 6. Build and release process

**Status: Missing.** This is B3 and it is the largest single gap between this
document and a deployable system.

What does not exist: `Dockerfile` (either app), `compose.yml`, `.dockerignore`,
systemd unit files, an image registry, a version-tagging scheme, a release
script, a changelog. `backend/scripts/` contains five scripts and **none is a
deploy-time tool** — they are a Windows dev-server shim, a manual extraction
evaluator, two contract exporters, and a manual operator case-runner.

### 6.1 Recommended: containers, one image per app

Both VMs then stay byte-identical and a rollback is a tag change.

```yaml
# /opt/draftly/compose.yml — identical on both VMs
services:
  api:
    image: ghcr.io/ORG/draftly-api:${TAG}
    env_file: /etc/draftly/backend.env
    ports: ["127.0.0.1:8000:8000"]
    command: uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 3
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://localhost:8000/health/ready"]
      interval: 15s
      timeout: 3s
      retries: 3
      start_period: 40s          # uvicorn needs boot room
    deploy:
      resources:
        limits: { cpus: "1.5", memory: 3g }

  worker:
    image: ghcr.io/ORG/draftly-api:${TAG}      # same image, different command
    env_file: /etc/draftly/backend.env
    command: python -m src.workers.runner
    restart: unless-stopped
    deploy:
      resources:
        limits: { cpus: "1.0", memory: 2g }

  # scheduler: NOT YET DEPLOYABLE — `--sched` does not exist. See §1.3.

  web:
    image: ghcr.io/ORG/draftly-web:${TAG}
    env_file: /etc/draftly/frontend.env
    ports: ["127.0.0.1:3000:3000"]
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://localhost:3000/"]
      interval: 15s
      start_period: 60s          # Next.js boots slower than uvicorn
    deploy:
      resources:
        limits: { cpus: "1.0", memory: 2g }
```

Resource limits are not decoration — two `e2-standard-2` boxes have 2 vCPU and
8 GB each, and Next.js SSR will pin CPU before the API does (§9.7).

Backend image: `python:3.12-slim`, `uv sync --frozen --no-dev`, non-root user.
Note `backend/pyproject.toml` pins **both** `psycopg2-binary` and
`psycopg[binary]`, and `fastapi[standard]` drags in `fastapi-cli`, `rich-toolkit`
and `sentry-sdk` — dead weight in a uvicorn-launched image. Trimming to
`fastapi` plus explicit extras is worth doing once, and would also stop
`sentry-sdk` appearing in dependency scans as an apparent error-reporting tool
the app does not actually use.

Frontend image: multi-stage `node:22-slim` (`.nvmrc` pins `22.16.0`),
`pnpm build`, then copy `.next/standalone`, `.next/static` and `public` into a
slim runtime stage — **which requires §6.2 first.**

### 6.2 `output: "standalone"` is missing

`frontend/next.config.ts` in full:

```ts
export default withNextIntl({
  reactStrictMode: true,
  poweredByHeader: false,
  outputFileTracingRoot: path.join(process.cwd(), ".."),
});
```

`outputFileTracingRoot` is set — a prerequisite for correct standalone tracing
in a monorepo, so the intent was there — but `output: "standalone"` itself never
landed. As written, `next build` produces a normal `.next` build and there is no
`.next/standalone` directory to copy. `frontend/package.json`'s `start` script
is `next start`, the non-standalone server, which is consistent with the config
and inconsistent with §1.1.

**Action:** add `output: "standalone"` before building any frontend image.

### 6.3 Build-time environment

`NEXT_PUBLIC_API_BASE_URL` is **baked in at build time** by Next.js. It must be
set to the public origin *before* `pnpm build`, not after. Rebuilding is the only
way to change it. Practical consequence: the frontend image is
environment-specific, so either build one image per environment or accept that
the same tag cannot serve staging and production.

### 6.4 Versioning and registry

- **Tag = git SHA.** Never `latest` in production.
- Registry: GHCR (`ghcr.io/ORG/…`) — the repo is already on GitHub Actions.
- Keep the last 10 tags so a rollback target always exists (§15).
- Sign or at minimum digest-pin images once the registry is in place.

### 6.5 Alternative: systemd, no Docker

Four units per VM — `draftly-api.service`, `draftly-web.service`,
`draftly-worker.service`, `draftly-scheduler.service` — each with
`Restart=always`, `EnvironmentFile=/etc/draftly/backend.env`, and a dedicated
`draftly` user. Deploy by `git pull && uv sync && pnpm build && systemctl restart`.

Containers win because the two VMs stay byte-identical and rollback is a tag
change rather than a `git checkout` plus rebuild. But note one thing in the
repo's favour for either path: `.gitattributes` contains `* text=auto eol=lf`,
which on a Windows dev box deploying to Linux VMs prevents a whole class of
`bad interpreter: /bin/bash^M` failures.

---

## 7. Database migration and rollback strategy

### 7.1 Current state

**Status: Partial.**

- 20 revisions in `backend/migrations/versions/`, single head
  (`matteragent0001`), with one legitimate branch-and-merge
  (`join_rta_and_l3_service_chains_merge0001.py`).
- `backend/migrations/env.py` connects with `DATABASE_URL_DIRECT`. Correct.
- **Every revision is additive.** No `alter_column`, no `drop_column`, no
  `rename`, no raw `op.execute`, no `drop_constraint` in any upgrade path. The
  only `drop_table` calls are inside `downgrade()`. Every `nullable=False`
  column is introduced on a new table with a `server_default`, so no backfill
  step is required.
- `alembic.ini` sets `timezone = UTC`.

That is a genuinely good position. The caveat is that because everything is
`create_table`, the migrations have never been exercised against a table that
already holds rows — the compatibility risk is unproven rather than absent.

### 7.2 Expand-then-contract, enforced

Migrations must be backward-compatible for **one release**, because during
deployment steps 3–5 (§2) VPS-1 runs old code against the new schema.

| Release | Action |
|---|---|
| N | Add the nullable column / new table. Deploy. Old code ignores it |
| N | Backfill in a job, not in the migration |
| N+1 | Start writing the new column. Deploy |
| N+2 | Drop the old column |

Three destructive operations are never acceptable in a single release: dropping
a column still read by the previous image, renaming a column, or narrowing a
type. Adding a `NOT NULL` column without a `server_default` is in the same class.

`docs/TESTING_PLAN.md` §5.3 specifies `test_no_destructive_ddl_in_upgrade_path`,
a static scan of `backend/migrations/versions/*.py`. That test is what makes
this section enforceable rather than aspirational. Until it exists, this is an
honour system.

### 7.3 Running migrations

Exactly once per release, from one place, against the direct URL:

```bash
docker run --rm --env-file /etc/draftly/backend.env \
  ghcr.io/ORG/draftly-api:$TAG \
  uv run alembic upgrade head
```

Never from a container that is also serving traffic, and never from both VMs.
There is no advisory lock guarding concurrent Alembic runs (§1.3), so "once,
from one place" is a procedural guarantee, not a technical one.

**Missing:** a wrapper script that takes a backup snapshot, runs
`alembic upgrade head`, verifies `alembic current == alembic heads`, and exits
non-zero on any failure. That script is the unit a CI job can call.

### 7.4 Migration rollback

**Status: Partial — the downgrade path has never been executed.**

Every revision has a `downgrade()`, and they drop the tables they created. Two
things are untested: whether the downgrades run cleanly in sequence, and whether
the merge revision downgrades correctly across its two parents.

| Situation | Response |
|---|---|
| Migration fails mid-run | Alembic runs each revision in a transaction. Investigate, fix forward. Do not re-run blindly |
| Migration succeeded, new code is broken | **Roll back the code, not the schema.** This is why expand-then-contract exists — the old image works against the new schema |
| Migration succeeded and is itself wrong | `alembic downgrade <previous-rev>` only if the revision is additive and no data was written to the new structure. Otherwise restore from backup (§12) |
| Data loss occurred | Stop. Restore from PITR (§12.2). Do not attempt a corrective migration on live data |

**The default is always "roll back the code, leave the schema."** A schema
rollback that discards rows written since the migration is a second incident on
top of the first.

---

## 8. CI/CD pipeline and quality gates

### 8.1 What exists

`.github/workflows/ci.yml`, two jobs, `ubuntu-latest`, 20-minute timeouts,
triggered on push to `main` and all pull requests.

**Job `verify`:** pnpm 10.23.0, Node 22.16.0, then `pnpm --dir frontend
typecheck`, `lint`, `build`, and `pnpm check:markdown`.

**Job `backend`:** self-activating via a `backend/pyproject.toml` probe, then
`uv lock --check`, `uv run ruff check .`, `uv run ruff format --check .`,
`uv run mypy src`, and `uv run pytest tests/unit tests/contract tests/conformance`.
Plus an inline `python3` heredoc validating `backend/contracts/services.yaml`.

### 8.2 Gaps

| Gap | Detail |
|---|---|
| **Frontend tests never run** | 13 vitest files. The root `pnpm check` script includes `test`; CI calls the four steps individually and omits it |
| **43 of 66 backend test files never run** | The explicit path list excludes `tests/security/`, `tests/privacy/`, `tests/integration/`, and all 30 co-located `src/modules/*/tests/` suites, despite `testpaths = ["src/modules", "tests"]` |
| **`tests/conformance` passes vacuously** | The directory contains only `.gitkeep`. It is named in the CI command and in `backend/contracts/services.yaml` as the enforcement point for service levels |
| **No Playwright** | 8 E2E specs, zero CI execution path |
| **No database service** | No `services:` block. DB-touching tests skip silently |
| **No coverage** | No `pytest-cov`, no `@vitest/coverage-v8`, no threshold |
| **No image build, scan, or push** | The pipeline ends at "tests passed". Nothing produces a deployable artifact |
| **No deploy job** | Deployment is entirely manual |
| **Floating action tags** | `@v4`/`@v5`; pin third-party actions to reviewed immutable SHAs |

The repo's own rubric already specifies a fuller pipeline.
`backend/docs/service-definition-of-done.md` §8:

```text
uv run ruff check . && uv run ruff format --check .
uv run mypy src
uv run pytest tests/unit tests/contract
uv run pytest tests/conformance          # parameterised over the registry
uv run pytest tests/integration          # needs PostgreSQL, MinIO, queue
uv run pytest tests/security
uv run pytest tests/e2e                  # the full matter-to-export path
uv lock --check
npx markdownlint-cli2
```

> "Conformance runs on every pull request. Integration and e2e run on every
> merge to `main` against a Neon branch database. The release-blocking set in §7
> runs on both and is **never skipped, never marked `xfail`, and never
> quarantined — a flaky release-blocker is fixed, not muted**."

The actual CI runs roughly the first three lines. Closing that gap is
`docs/TESTING_PLAN.md` commits 1–4.

### 8.3 Target pipeline

| Stage | Job | Trigger | Gate |
|---|---|---|---|
| 1 | `verify` | every PR | typecheck, lint, build, **vitest + coverage**, markdown |
| 2 | `backend` | every PR | ruff, format, mypy, `uv lock --check`, **full pytest + coverage**, Postgres service |
| 3 | `conformance` | every PR | `tests/conformance` parameterised over `services.yaml` — must contain real tests first |
| 4 | `e2e` | every PR | Playwright against a production build, 2 retries, HTML + JUnit artifacts |
| 5 | `build` | push to `main` | Build both images, tag with the git SHA, **Trivy scan**, push to GHCR |
| 6 | `neon` | push to `main` | `-m integration` against a real Neon branch; `alembic upgrade head` then `downgrade base` |
| 7 | `deploy-staging` | push to `main`, automatic | Migrate, roll VPS-2, roll VPS-1, smoke test (§10.3) |
| 8 | `deploy-production` | tag `v*`, **manual approval** | Same, with the §16 checklist |
| 9 | `live` | `workflow_dispatch` only | `-m live` — Gemini, Vision, GCS. Costs money |

Release-blocking gates that must be green on every run, from
`backend/docs/service-definition-of-done.md` §7 — eleven of them, each already
mapped to a named test:

invented citation · unsupported retained legal claim · cross-matter disclosure ·
cross-organisation disclosure · silent original loss · mandatory unverified fact
in an approved export · altered locked wording · hidden placeholder · missing
audit event · approval attached to changed content · legal source crossing its
approved boundary.

Of those eleven, `documents/test_immutability.py` exists and passes. The
tenancy and audit-coverage ones depend on `tests/conformance/`, which is empty.

---

## 9. Tests required before deployment

`docs/TESTING_PLAN.md` is canonical. This section states only the gating
relationship.

### 9.1 Gate by environment

| Target | Must be green |
|---|---|
| Staging | `verify` + `backend` (full suite) + `conformance` + `e2e` |
| Production | All of the above, plus `neon`, plus the eleven release blockers, plus a green §16 checklist from the preceding staging deploy |

No deployment proceeds with a known-failing release blocker. Per DoD §8 these
are "never skipped, never marked `xfail`, and never quarantined."

### 9.2 Open findings that gate production

From `docs/TESTING_PLAN.md` §0, the four Critical ones are all deployment-relevant:

- **F1** — the real token path is never executed by any test. No test has
  observed a 401 from a missing, expired, or tampered token. Deploying auth
  changes is currently unverifiable.
- **F2** — `src/workers/runner.py` has no test file. The outbox claim, retry,
  and dead-letter path is what stands between a failed job and silent data loss.
- **F3** — Playwright has no auth strategy; seven of eight specs fail on
  startup, so the E2E gate in §8.3 stage 4 cannot yet be met.
- **F4** — HMAC-signed pagination cursors have no test, and
  `api_cursor_signing_key` defaults to `""` (§4.3).

### 9.3 Load testing

Run after a successful staging deploy, from a **third machine** — running the
generator on a VM under test invalidates the numbers. k6 is the right tool:
scriptable, produces p95/p99 directly, and supports thresholds that fail the run.

| # | Test | Shape | What it proves |
|---|---|---|---|
| 1 | Smoke | `curl`, `ab -n 200 -c 10` | It is up and TLS works |
| 2 | Health baseline | 50 VUs, 2 min | Raw LB + nginx capacity, no DB |
| 3 | Authenticated read | ramp 0→200 VUs, 10 min | The real API path including Neon |
| 4 | Upload / write | 20 VUs, 5 min, 2 MB PDFs | Worker, GCS, the 50 MB cap |
| 5 | Soak | 50 VUs, 60 min | Memory leaks, pool exhaustion |
| 6 | Spike | 10→500 VUs in 30 s | Absence of autoscaling, graceful degradation |
| 7 | Failover | kill VPS-2 mid-test-3 | nginx ejects a dead backend |
| 8 | Rolling deploy | redeploy mid-test-3 | The zero-downtime claim is true |

```javascript
// read-load.js — test 3
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '2m', target: 50 },
    { duration: '5m', target: 200 },
    { duration: '2m', target: 0 },
  ],
  thresholds: {
    http_req_failed:   ['rate<0.01'],
    http_req_duration: ['p(95)<800', 'p(99)<2000'],
  },
};

const headers = { Authorization: `Bearer ${__ENV.CLERK_JWT}` };

export default function () {
  const matters = http.get(`${__ENV.BASE_URL}/api/v1/matters`, { headers });
  check(matters, { 'matters 200': (r) => r.status === 200 });

  const body = matters.json();
  if (body?.items?.length) {
    const issues = http.get(
      `${__ENV.BASE_URL}/api/v1/matters/${body.items[0].id}/issues`, { headers });
    check(issues, { 'issues 200': (r) => r.status === 200 });
  }
  sleep(Math.random() * 2 + 1);
}
```

**Getting a test token** is the awkward part. Best first: Clerk testing tokens
or a long-lived JWT template made for load tests; a dedicated staging deploy
with `USE_STUB_IDENTITY=true`; or sign in once with Playwright and reuse the
session cookie. Option two is cleanest — **never point a 500-VU load test at
Clerk's production API**, or you will be rate-limited and will measure Clerk
rather than Draftly.

### 9.4 Failover test

```bash
# terminal 1 — steady load
k6 run -e BASE_URL=... -e CLERK_JWT=$TOKEN read-load.js

# terminal 2 — 60s in, kill VPS-2
gcloud compute instances stop draftly-app --zone asia-south1-c

# terminal 3 — on VPS-1, watch nginx eject it
sudo tail -f /var/log/nginx/error.log | grep -i upstream
```

**Pass criteria:** `max_fails=3` means up to 3 failed requests per worker
process before the backend is marked down, then `fail_timeout=15s` before retry.
With `proxy_next_upstream` set, most of those retry onto VPS-1 and never reach
the user. Realistic target: **under 1% errors and full recovery inside 15 s**.
p95 roughly doubles — one VM doing two VMs' work — but there must be no
sustained 5xx.

**Also run the inverse and be honest about it.** Stop `draftly-edge` instead.
The site goes fully down, because VPS-1 holds the only public IP:

```bash
gcloud compute instances delete-access-config draftly-edge --zone asia-south1-a
gcloud compute instances add-access-config draftly-app --zone asia-south1-c \
  --address draftly-ip
```

Time that procedure and record it. A measured five-minute manual failover is a
legitimate finding; an unmeasured claim of "highly available" is not.

### 9.5 Rolling-deploy test

Under steady 100-VU load, redeploy VPS-2 then VPS-1 per §2. **Pass criteria:
zero 5xx.** If you see 502s the cause is almost always one of: the container was
marked healthy before Next.js finished booting (raise `start_period`); nginx
reused a keepalive connection to a container that just died (confirm
`proxy_next_upstream error timeout http_502 http_503`); or both VMs restarted at
once.

### 9.6 Targets to record

| Metric | Target |
|---|---|
| p50 latency (read) | < 200 ms |
| p95 latency (read) | < 800 ms |
| p99 latency (read) | < 2 s |
| Error rate | < 1% |
| Throughput at 200 VUs | ≥ 150 req/s |
| Upload p95 (2 MB) | < 5 s, excluding async extraction |
| Failover: VPS-2 dies | ≤ 15 s to recover |
| Failover: VPS-1 dies | measure it, do not claim it |
| Rolling-deploy 5xx | 0 |
| Soak memory growth | < 10% over 60 min |

Record per run: the k6 summary, nginx access-log latency on VPS-1, per-VM
CPU/memory, Neon connection count, and outbox backlog depth. Also record **the
split of requests across the two VMs** — if VPS-2's access log is empty, the
load balancer is not balancing and every other number is meaningless.

### 9.7 Likely bottlenecks

1. **Neon connection limit.** Each uvicorn worker holds a SQLAlchemy pool.
   3 workers × 2 VMs × pool_size 5 = 30 connections, plus workers. Symptom:
   `/health/ready` flaps under load and the LB ejects healthy VMs. Fix: use the
   pooled endpoint (already the default), cap `pool_size`, raise `max_overflow`
   carefully.
2. **Neon autosuspend cold start.** The first request after idle takes seconds.
   Warm it before the run or the ramp-up numbers are meaningless.
3. **Gemini rate limits.** Test 4 will hit them. Use `EXTRACTION_PROVIDER=stub`
   on staging to load-test the platform, and test Gemini separately with a small
   honest number of concurrent extractions.
4. **Region latency.** A generator in Europe against `asia-south1` adds ~150 ms
   to every number. State the generator's location in the report.
5. **Next.js SSR CPU.** The frontend, not the API, usually pins CPU first. If
   test 3 shows web CPU at 95% and API at 30%, add a CDN for static assets
   before adding VMs.

---

## 10. Health checks and smoke tests

### 10.1 The endpoints

**Status: Ready.** `backend/src/main.py`:

| Route | Returns | Status code | Auth |
|---|---|---|---|
| `GET /health/live` | `{"status": "ok"}` | always 200 | none |
| `GET /health/ready` | `{"status": "ok", "db": "ok"}` or `{"status": "degraded", "db": "unreachable"}` | 200 / **503** | none |

Neither echoes credentials, connection strings, versions, or settings. Both are
correct and the distinction between them is the right one.

**Balance the load balancer on `/health/ready`, never `/health/live`.** A VM
whose Neon pool is exhausted is `live` but cannot serve a single real request;
routing to it produces 500s that look like application bugs. Use `/health/live`
only to answer "should I restart this container".

Nothing currently tests either endpoint (`docs/TESTING_PLAN.md` §8.4), including
the 503 branch the whole topology depends on.

### 10.2 Active vs passive checking

nginx's `max_fails`/`fail_timeout` is a **passive** check — it only reacts after
real requests fail into it, so up to three users eat an error before the VM is
ejected. Two ways to close the gap:

1. **Container healthchecks (free, do this).** The compose healthcheck in §6.1
   hits `/health/ready` every 15 s, so a hung API is restarted before nginx sees
   it. `start_period: 40s` for uvicorn, `60s` for Next.js.
2. **Active upstream probing.** Stock nginx keeps this in NGINX Plus. Free
   routes: swap nginx for **HAProxy** on VPS-1 (`option httpchk GET /health/ready`
   plus `server … check inter 5s fall 3 rise 2`, which also gives a stats page),
   or keep nginx and run a systemd timer that curls each backend and rewrites the
   upstream file on a state change. The §1.2 topology does not change either way
   — only the program listening on :443.

### 10.3 Smoke test

**Status: Missing.** No smoke test exists. Add `scripts/smoke.sh`, runnable
against any environment, exiting non-zero on the first failure:

```bash
#!/usr/bin/env bash
set -euo pipefail
BASE="${1:?usage: smoke.sh https://host}"

curl -fsS "$BASE/health/live"  | grep -q '"status":"ok"'
curl -fsS "$BASE/health/ready" | grep -q '"db":"ok"'

# TLS is valid and not near expiry
echo | openssl s_client -connect "${BASE#https://}:443" 2>/dev/null \
  | openssl x509 -noout -checkend 604800

# unauthenticated API call is refused, and with the error envelope
test "$(curl -s -o /dev/null -w '%{http_code}' "$BASE/api/v1/matters")" = 401
curl -s "$BASE/api/v1/matters" | grep -q '"correlationId"'

# correlation id is echoed
curl -sI -H 'X-Correlation-Id: smoke-test' "$BASE/health/live" \
  | grep -qi 'x-correlation-id: smoke-test'

# the frontend renders
curl -fsS "$BASE/" | grep -qi '<html'

# security headers are present (§13.3 — these come from nginx, not the app)
curl -sI "$BASE/" | grep -qi 'strict-transport-security'

# BOTH VMs are serving — if one access log stays empty the LB is not balancing
echo "smoke: OK"
```

Wire it as the last step of every deploy job (§8.3 stages 7 and 8) and as the
first step of §16.

---

## 11. Logging, monitoring, tracing and alerts

**Status: Missing.** This is the weakest area in the entire system, and it is
the one that determines whether the §9 load-test numbers can ever be explained
or the §15 rollback triggers ever detected.

### 11.1 What exists

Structured logs, and nothing else. `backend/src/platform/observability/logging.py`
is 51 lines and is the complete observability layer: structlog with
`merge_contextvars`, `add_log_level`, ISO `TimeStamper`, `StackInfoRenderer`,
then `ConsoleRenderer` if `sys.stderr.isatty()` else `JSONRenderer`. Under
systemd or Docker stderr is not a TTY, so production gets JSON. Correlation IDs
are generated or accepted per request in `backend/src/main.py` and echoed as
`X-Correlation-Id`.

The exception handling is genuinely careful: `unhandled_exception_handler` logs
only `exc_type`, `path`, and `correlation_id`, deliberately not the message,
because "exception messages may contain SQL parameter sets, provider payloads,
or extracted document values."

### 11.2 What does not exist

**Confirmed by exhaustive search** for `prometheus|opentelemetry|otel|sentry|statsd|datadog|newrelic`
across `backend/` and `frontend/`: zero hits in any source file. The only
matches anywhere are `sentry-sdk` as a transitive dependency of
`fastapi[standard]`'s CLI chain in `backend/uv.lock`, and `@opentelemetry/api`
as an optional peer declaration in `frontend/pnpm-lock.yaml`. Neither is
imported. Neither is instrumentation.

So there is: no `/metrics` endpoint, no request-duration histograms, no error
rate by route, no spans, no error aggregation, no uptime check, no alerting of
any kind. An operator's only signals are nginx access logs and the
`/health/ready` 200/503 flip.

Five further defects in what does exist:

1. **Log level is not runtime-configurable.** `configure_logging("DEBUG" if
   settings.environment == "local" else "INFO")` is the only call site. There is
   no `LOG_LEVEL` variable, and `cache_logger_on_first_use=True` freezes the
   level after the first log call. Raising verbosity during an incident requires
   a code change or flipping `ENVIRONMENT`, which would also re-enable `/docs`.
2. **Two interleaved log formats.** `PrintLoggerFactory()` writes straight to
   stdout and bypasses stdlib `logging`, so uvicorn access logs, SQLAlchemy
   logs, and every third-party library are neither JSON nor correlation-tagged.
   A deployed host emits a mix. Fix with a `structlog.stdlib.ProcessorFormatter`
   bridge.
3. **`user_id` is never bound.** The module's own docstring says "always bind
   correlation_id and user_id when authenticated", but the middleware calls
   `bind_request_context(correlation_id)` with no user, and nothing re-binds
   after authentication. Every log line carries `user_id=""`, so logs cannot be
   attributed to an account during an incident.
4. **No tracebacks.** `format_exc_info` / `dict_tracebacks` are absent from the
   processor chain, so `exc_info=True` renders nothing. Crash diagnosis depends
   entirely on correlation ID plus `exc_type`.
5. **`configure_logging()` runs inside `lifespan`**, after `create_app()` has
   already executed at import. Anything logged during import or router
   registration goes through an unconfigured structlog.

### 11.3 Minimum viable, in priority order

1. **Ops Agent on both VMs** → CPU, memory, disk, and `/var/log` to Cloud
   Logging. One `gcloud` command per VM. This alone makes logs searchable across
   two machines instead of requiring SSH and grep.
2. **Fix the three log defects that cost nothing**: bind `user_id` after auth,
   add a `LOG_LEVEL` setting, add the stdlib bridge.
3. **Uptime check** on `https://draftly.example.lk/health/ready` every 60 s with
   an email alert. This is the single highest-value monitor and takes minutes.
4. **Structured log metrics.** Cloud Logging log-based metrics over the JSON
   fields give error rate and latency buckets without adding a dependency.
5. **Prometheus later, if needed.** `prometheus-fastapi-instrumentator` adds a
   `/metrics` endpoint in a few lines. Do not add it before items 1–4.

### 11.4 Alerts worth having

| Alert | Threshold | Why |
|---|---|---|
| 5xx rate | > 1% for 5 min | §15 rollback trigger |
| p95 latency | > 2 s for 10 min | §15 rollback trigger |
| `/health/ready` failing | either VM, 2 consecutive | LB is about to eject a VM |
| VM CPU | > 85% for 10 min | Capacity — Next.js SSR usually first |
| **Outbox pending rows older than 10 min** | any | **The worker is stuck. Draftly-specific and the easiest failure to miss** |
| **Any dead-letter arrival** | any | A job has permanently failed. `backend/docs/jobs-and-workers.md` §8: "Dead-letter is a visible state, not a log line" |
| **Lease-reaper activity above baseline** | any | Per `jobs-and-workers.md` §8, this means workers are crashing |
| Neon connection count | > 80% of limit | §9.7 bottleneck 1 |
| **`provider_data_approval` enabled** | any change to true | `backend/docs/infrastructure.md` lists this as an alert condition in its own right |
| TLS certificate expiry | < 14 days | certbot renewal failed silently |

---

## 12. Backup and disaster recovery

**Status: Missing.** B5.

`backend/docs/infrastructure.md` is blunt about how this section came to exist:
"Plan §10 requires this before lawyer testing, **and it was not written down**."
It is now written down, and still not executed.

### 12.1 Targets

| Target | Value | Status |
|---|---|---|
| RPO | 15 minutes | **Unconfirmed** — "Confirm with the practice before production" |
| RTO | 4 hours | **Unconfirmed** — same |

Until the practice confirms these, they are engineering guesses about a legal
business's tolerance for losing a day's conveyancing work.

### 12.2 Database

- **V0 (Neon):** point-in-time restore. Verify the retention window on the
  actual plan tier — the free tier's window is shorter than most people assume,
  and nobody has checked.
- **V1 (self-hosted):** nightly `pg_dump` plus continuous WAL archiving to
  separate storage. Retain 30 daily and 12 monthly.

### 12.3 Object storage

Evidence bytes in GCS are **the irreplaceable asset** — a lost deed scan cannot
be regenerated, unlike a derived fact.

- **Enable object versioning on the bucket.** Not currently asserted anywhere;
  `_assert_bucket_policy` checks uniform bucket-level access, public-access
  prevention, and region, but **not versioning**. Add it to that assertion.
- Enable a retention policy consistent with `retention_service` once the
  retention periods clear legal review — they are an open item in
  `backend/docs/services/README.md` §6.
- Consider dual-region or a scheduled transfer to a second bucket.

### 12.4 The restore drill

> "**Restore drill**: quarterly, into an isolated environment, timed. **A
> restore that has never been executed is not a backup.**"
> — `backend/docs/infrastructure.md`

No restore has ever been executed. Schedule the first one **before** any real
client data lands, not after. Drill procedure:

1. Restore the database to a throwaway Neon branch at a chosen timestamp.
2. Restore a sample of object-storage versions to a scratch bucket.
3. Point a staging deploy at both.
4. Run `scripts/smoke.sh` (§10.3) plus a manual walk of one matter.
5. **Time it end to end and record the number.** That number, not the 4-hour
   target, is the real RTO.
6. Post-restore reconciliation, which
   `backend/docs/infrastructure.md` marks mandatory: "A restore can reinstate
   records that were lawfully destroyed." Anything `retention_service` disposed
   of before the restore point must be re-disposed after it.

Step 6 is a legal obligation, not housekeeping, and it is the step most likely
to be skipped.

### 12.5 Scenarios

| Scenario | Response | RTO |
|---|---|---|
| One app container dies | Docker restarts it; nginx ejects it meanwhile | seconds |
| VPS-2 down | Site serves from VPS-1 at ~2× latency. Worker stops, outbox backs up but loses nothing | until reboot |
| **VPS-1 down** | **Whole site down** — it holds the only public IP. Reassign the static IP to VPS-2 and enable its TLS block | ~5 min, measured in §9.4 |
| Zone outage | Same as losing one VM; the VMs are in different zones deliberately | as above |
| **Region outage** | **Everything is down.** Both VMs are in `asia-south1`. No plan exists | unbounded |
| Neon unavailable | Both VMs return 503, `/health/ready` fails. Nothing local to do | provider-dependent |
| Data corruption | PITR to just before, then §12.4 steps 4–6 | 4 h target, unmeasured |
| Bucket deletion | Object versioning — **if enabled, which it is not asserted to be** | unknown |

---

## 13. Security checks and access controls

### 13.1 What is strong

The application-layer authorization model is the best-engineered part of this
codebase, and it is enforced in code rather than described in a document.

- **Two independent gates**, per `backend/docs/security-model.md`: "A paid plan
  never grants a capability, and a capability never bypasses a plan or quota."
- **Tenancy first, always.** Filter by `ctx.actorId` before checking matter
  ownership before checking capability. "A client-supplied user id never
  establishes tenancy."
- **Existence hiding.** A caller who does not own a matter gets a 404
  byte-identical to a nonexistent one; "a 403 would confirm the matter is real."
  A denied privileged attempt is audited even when the caller sees a 404.
- **Capabilities are not additive by seniority**, and a capability absent from
  the map is denied.
- **The agent is never a principal**: `effective = user capabilities ∩ tool
  allowlist ∩ matter ownership`, never a union, so a prompt injection reaching
  for a prohibited action fails at the executor rather than at the model's
  discretion.
- **Fail-closed boot guards** (§4.5), covered by 19 tests.
- **Audit is a per-user hash chain**, so a deleted or edited entry is detectable.
- **Identifiers encrypted at rest** with a blind index; reading one back requires
  a stated `purpose`.

### 13.2 What is missing

| Gap | Detail | Severity |
|---|---|---|
| **No rate limiting** | `backend/docs/api-conventions.md` §8 specifies per-organisation, per-route-class limits (`read`, `write`, `expensive`, `webhook`). No limiter, no middleware, no per-route throttle exists anywhere in `backend/src/` | High — brute force, and cost amplification on Gemini |
| **No security headers from the app** | `frontend/next.config.ts` has no `headers()`. No CSP, HSTS, X-Frame-Options, Referrer-Policy, Permissions-Policy. nginx is the only place they can come from (§5.2) | High |
| **No container scanning** | No Trivy or equivalent in CI. §8.3 stage 5 adds it | Medium |
| **No dependency scanning** | No Dependabot config, no `pip-audit`, no `pnpm audit` in CI. Every backend dependency is a `>=` floor with no upper bound; reproducibility rests entirely on `uv.lock` | Medium |
| **B2 tenancy key unresolved** | `user_id` in code vs `organisation_id` in `events.md` §2, the outbox DDL, the Idempotency-Key tuple, and DoD §4.1.5. Self-declared as blocking L2 for every service | High |
| **Matter ownership not wired** | `backend/docs/security-model.md`: authorization for matter mutations is "capability-only … **until ownership checks are wired in `matter_service`**". The 404-not-403 guarantee is conditional on work not yet done | High |
| **`X-Correlation-Id` accepted unvalidated** | No length cap, no format check, echoed and logged. Log-forging vector; structlog's JSON renderer escapes it, so impact is low | Low |
| **`RequestValidationError` / `HTTPException` bypass the error envelope** | No handler registered for either, so their bodies do not match the contract every other error follows | Low |
| **`/docs` exposed on staging** | §3.1 | Medium |

### 13.3 Pre-deploy security checklist

- [ ] TLS via certbot, auto-renewal verified by actually waiting for one renewal
- [ ] Security headers set in nginx (§5.2) and verified by `scripts/smoke.sh`
- [ ] SSH via IAP only; no public port 22 on either VM
- [ ] VPS-2 has no public IP; `allow-internal-app` sourced from `10.128.0.0/20` only
- [ ] Secrets in Secret Manager or `/etc/draftly/*.env` mode 0600 root, never in an image
- [ ] All five gate flags (§4.5) explicitly set, not defaulted
- [ ] `USE_STUB_IDENTITY=false`, `EXTRACTION_PROVIDER` not `stub`, `SOURCE_FILE_STORAGE=object_storage`
- [ ] `USE_STUB_BILLING` explicitly set — it defaults to `True` (§4.3)
- [ ] `API_CURSOR_SIGNING_KEY`, `PARTY_IDENTIFIER_KEY`, `PARTY_BLIND_INDEX_KEY` set to real values
- [ ] `CLERK_AUTHORIZED_PARTY` equals the public origin; `sk_live_` keys in use
- [ ] `DRAFTLY_GCS_LOCATION` set — empty disables the residency check (§4.4)
- [ ] GCS bucket: uniform bucket-level access, public access prevention enforced, **versioning on**
- [ ] Runtime identity holds `storage.buckets.get` (§4.6 IAM note)
- [ ] Container image scanned, running as non-root, resource limits set
- [ ] `/docs` and `/redoc` confirmed unreachable
- [ ] Rate limiting in place, or the absence explicitly accepted and recorded

### 13.4 Cross-check that must not drift

`client_max_body_size 50m` in nginx must equal `MAX_SOURCE_FILE_BYTES`
(52428800). If nginx is smaller it 413s before FastAPI can return its error
envelope, and the user sees a bare nginx page instead of a message.
`docs/TESTING_PLAN.md` §9.1 pins the constant in a unit test; the nginx config
should carry a comment citing it, as §5.2 does.

---

## 14. Zero-downtime strategy

**Status: Partial.** Rolling deployment is viable and is the right choice here.

| Strategy | Verdict |
|---|---|
| **Rolling** | **Chosen.** The app tier is stateless, the LB health-checks `/health/ready`, and two VMs give exactly the capacity to take one out at a time |
| Blue-green | Needs double the infrastructure. Revisit if the budget grows |
| Canary | Needs traffic splitting the self-hosted nginx does not do well, and per-variant metrics that do not exist (§11) |
| Recreate | A maintenance window. Only for the cases in §14.2 |

### 14.1 How rolling achieves zero downtime

Steps 3–5 of §2 work because the LB health-checks `/health/ready` and so never
sends traffic to a VM that is mid-restart, `proxy_next_upstream` retries the
other VM on a connection failure, and the app tier holds no state that a
restart could lose. Requirements: one VM at a time, migrations backward-
compatible for one release (§7.2), and `start_period` long enough that a
container is not marked healthy before Next.js finishes booting.

### 14.2 When a maintenance window is unavoidable

- A migration that cannot be made backward-compatible — a type narrowing, a
  destructive rename, a table rewrite.
- A Neon plan or region change.
- The V1 cutover to self-hosted Postgres (§5.5).
- Any restore from backup (§12.4).

Window procedure: announce, put nginx into a static maintenance page, drain,
migrate, deploy both VMs, smoke test (§10.3), reopen. Target under 30 minutes
and schedule outside Sri Lankan business hours. Never on a Friday.

### 14.3 The honest weakness

**VPS-1 is a single point of failure.** It holds the only public IP and runs the
load balancer, so losing it takes the site down even though VPS-2 is healthy.
This is inherent to self-hosting a load balancer on one of only two machines —
it is not a configuration mistake, and it is why §9.4 says to measure the manual
failover rather than describe the setup as highly available.

The upgrade, when it stops being acceptable: move balancing off VPS-1 entirely
onto GCP's External Application Load Balancer — an anycast IP in front of both
VMs, so neither is special.

```bash
gcloud compute health-checks create http hc-api \
  --port 80 --request-path /health/ready \
  --check-interval 10s --timeout 5s \
  --healthy-threshold 2 --unhealthy-threshold 3

gcloud compute instance-groups unmanaged create ig-a --zone asia-south1-a
gcloud compute instance-groups unmanaged add-instances ig-a \
  --instances draftly-edge --zone asia-south1-a
gcloud compute instance-groups unmanaged set-named-ports ig-a \
  --named-ports http:80 --zone asia-south1-a
# repeat for ig-b / draftly-app in asia-south1-c

gcloud compute backend-services create bs-api --global \
  --protocol HTTP --port-name http --health-checks hc-api \
  --timeout 120s --connection-draining-timeout 60s --session-affinity NONE
gcloud compute backend-services add-backend bs-api --global \
  --instance-group ig-a --instance-group-zone asia-south1-a
# add ig-b; repeat for bs-web against hc-web

gcloud compute url-maps create draftly-map --default-service bs-web
gcloud compute url-maps add-path-matcher draftly-map \
  --path-matcher-name api-matcher --default-service bs-web \
  --backend-service-path-rules "/api/*=bs-api,/health/*=bs-api"

gcloud compute ssl-certificates create draftly-cert --global \
  --domains draftly.example.lk          # Google-managed, no certbot
gcloud compute target-https-proxies create draftly-https \
  --url-map draftly-map --ssl-certificates draftly-cert
gcloud compute forwarding-rules create draftly-fr-https --global \
  --target-https-proxy draftly-https --ports 443
```

What changes on the VMs: **almost nothing.** Both keep their thin local nginx on
:80, VPS-1 drops its TLS block and upstream pool, both get the LB health-check
ranges (`130.211.0.0/22`, `35.191.0.0/16`) in the firewall, and DNS moves to the
LB's IP. The app, the containers, and the private-VPC design are untouched —
which is exactly why the nginx design is safe to start with.

Cost: a few USD/month for the forwarding rule plus egress. Buys active health
checks, Google-managed certificates, HTTP/3, Cloud Armor, and Cloud CDN. Start
with nginx; move here the moment real client matters are on the platform.

---

## 15. Rollback triggers and procedure

**Status: Missing.** There is currently nothing to roll back *to* — no tagged
images, no previous release. This section is the target state and depends on §6.

### 15.1 Triggers

**Automatic rollback** — no discussion, no approval:

| Trigger | Threshold |
|---|---|
| `/health/ready` failing on both VMs | 3 consecutive checks |
| 5xx rate | > 5% for 2 min |
| p95 latency | > 5 s for 5 min |
| Smoke test fails post-deploy | any assertion |
| Any release-blocking behaviour observed in production | immediately |

**Human decision within 15 minutes:**

| Trigger | Threshold |
|---|---|
| 5xx rate | 1–5% for 5 min |
| p95 latency | 2–5 s for 10 min |
| Outbox dead-letter arrivals | any new |
| A single tenant reporting data they should not see | **immediately, and treat as a security incident** |

**Do not roll back for:** a cosmetic UI defect, a slow single endpoint with no
error-rate change, or one user's failed request. Fix forward.

### 15.2 Procedure

```bash
# 0. Declare. Post in #incidents with the deploying SHA and the trigger.

# 1. Identify the previous good tag
ssh draftly-edge 'docker images ghcr.io/ORG/draftly-api --format "{{.Tag}}"' | head -5
PREV=<previous git sha>

# 2. Roll VPS-2 back first (same order as forward — the non-edge VM leads)
gcloud compute ssh draftly-app --zone asia-south1-c --tunnel-through-iap
  sudo TAG=$PREV docker compose -f /opt/draftly/compose.yml up -d
  curl -fsS http://127.0.0.1:8000/health/ready     # must return db: ok

# 3. Confirm VPS-1's nginx is routing to VPS-2 again
ssh draftly-edge 'sudo tail -20 /var/log/nginx/access.log'

# 4. Roll VPS-1
gcloud compute ssh draftly-edge --zone asia-south1-a --tunnel-through-iap
  sudo TAG=$PREV docker compose -f /opt/draftly/compose.yml up -d
  curl -fsS http://127.0.0.1:8000/health/ready

# 5. Verify
./scripts/smoke.sh https://draftly.example.lk

# 6. LEAVE THE SCHEMA ALONE unless the migration itself is the fault (§7.4)
```

**Target: under 10 minutes from trigger to verified.** Time it during the §9.5
rolling-deploy test so the number is known before it is needed.

### 15.3 What rollback does not fix

- **Data written by the bad release.** A rollback restores the code, not the
  rows. If the bad release wrote wrong facts or wrong audit entries, that is a
  separate remediation.
- **A migration that destroyed data.** §7.4 — restore from backup, do not
  migrate forward over it.
- **Anything external.** A Gemini or Clerk outage is not fixed by rolling back.
- **Emails and webhooks already sent.** Resend deliveries and PayHere
  callbacks are not reversible.

### 15.4 After every rollback

Write a postmortem within 48 hours, blameless: timeline in UTC, root cause,
impact, and action items with owners and deadlines. Add a test that would have
caught it — that test is the actual deliverable of the incident.

---

## 16. Post-deployment verification checklist

Run in order. Any failure stops the deploy and triggers §15.

### Immediate — within 5 minutes

- [ ] `./scripts/smoke.sh https://draftly.example.lk` passes end to end
- [ ] `curl -fsS https://draftly.example.lk/health/live` → `{"status":"ok"}`
- [ ] `curl -fsS https://draftly.example.lk/health/ready` → `"db":"ok"`
- [ ] TLS certificate valid, correct hostname, not expiring within 14 days
- [ ] **Both VMs are serving.** Hit the site 20× and watch both access logs — if
      VPS-2's is empty the LB is not balancing
- [ ] `alembic current` equals `alembic heads`
- [ ] No 5xx in nginx logs on either VM since the deploy timestamp
- [ ] Worker is claiming: outbox `pending` count is not monotonically rising
- [ ] Container status `Up` and `healthy` for every service on both VMs

### Functional — within 15 minutes, staging or a synthetic production matter

- [ ] Sign in via Clerk with a real account — this is the F1 path that no test covers
- [ ] Create a matter; it reaches `intake` and compiles a checklist
- [ ] Upload a synthetic PDF; it stores and processes
- [ ] Verify a fact; it moves to `verified` with an evidence span
- [ ] Run checks; blocking issues surface
- [ ] Generate a draft; it is refused if a mandatory fact is unverified
- [ ] Approve and export a draft; the artifact downloads
- [ ] **Sign in as a second user and confirm the first user's matter returns
      404, not 403** — the §13.1 existence-hiding guarantee
- [ ] Audit events appear for every mutation above
- [ ] Sinhala locale toggle works if `MULTILINGUAL_LANGUAGE_SUPPORT=true`

### Configuration — confirm, do not assume

- [ ] `ENVIRONMENT=production`; `/docs` and `/redoc` return 404
- [ ] `SOURCE_FILE_STORAGE=object_storage`; a file written from one VM is
      readable from the other
- [ ] `USE_STUB_IDENTITY=false`, `USE_STUB_BILLING` explicitly set,
      `EXTRACTION_PROVIDER` not `stub`
- [ ] All five gate flags (§4.5) hold their intended values
- [ ] `CLERK_AUTHORIZED_PARTY` is the public origin
- [ ] Clock synchronised on both VMs (`timedatectl`) — Clerk JWT drift
- [ ] Log output is JSON and carries a correlation ID

### Within 24 hours

- [ ] Error rate under 1% over the full period
- [ ] p95 latency within the §9.6 target
- [ ] No memory growth trend on either VM
- [ ] Outbox has no dead-letter arrivals
- [ ] Neon connection count is well under the plan limit
- [ ] Any scheduled job that should have fired, fired — **currently this means
      checking that nine of them did not, per §1.3**
- [ ] Record the deployment: SHA, timestamp, operator, anything unexpected

---

## 17. Known risks, blockers and assumptions

### 17.1 Blockers — nothing ships past these

Restating §0 with detail.

**B1 — PDPA 2022 approvals.** `backend/docs/infrastructure.md`: real client
matter data may reach managed cloud infrastructure only once data residency, a
processor agreement, and lawyer sign-off are confirmed, and this "applies to
Neon, Google Cloud Storage, Document AI, Gemini, Resend, and PayHere alike, and
hardest to the OCR path, where the payload is the deed itself." Until then this
deployment runs on synthetic and pilot data only. The gate flags in §4.5 enforce
it in code, which is the right design — do not work around them.

**B2 — The tenancy key.** `backend/docs/security-model.md` §2.1 is explicit:
"Status: open. Owner: the platform team. **Blocks L2 for every service.**" The
code ships `user_id` and no `organisation_id`; `events.md` §2 requires
`organisationId` on every event; DoD §4.1.5 requires a non-null
`organisation_id` column on every table and tests for it; the outbox DDL and the
Idempotency-Key tuple both assume it. A new service cannot satisfy all three.
"Both are one-way doors for the schema, so this is not a per-service call."

**B3 — No build artifacts.** §6.

**B4 — No scheduler.** §1.3. Nine scheduled jobs have no runtime, two of them
legally significant (retention evaluation, monthly register close).

**B5 — Untested backups.** §12.4.

**B6 — `landing-page/`.** §17.3.

**B7 — Four Critical test findings.** §9.2.

### 17.2 Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **VPS-1 loss takes the site down** | Medium | High | Inherent to the design. Measure the manual failover (§9.4); upgrade path in §14.3 |
| **No observability delays every diagnosis** | High | High | §11.3 items 1–3 are hours of work |
| **Region loss** | Low | Total | Both VMs are in `asia-south1`. No plan exists. State it plainly |
| **Neon connection exhaustion** | Medium | High | §9.7. Cap `pool_size`; alert at 80% |
| **Gemini rate limits or cost spike** | Medium | Medium | §9.7. The §1.3 lease bug would double-bill if processing moves to the worker |
| **Secrets leak via a wholesale tree copy** | Medium | Critical | `backend/.env` holds real secrets. Deploy from an image, never `rsync` the tree (§4.6) |
| **No autoscaling** | High | Medium | Two fixed VMs. The §9.3 spike test finds the ceiling; a managed instance group is the next step and changes no application code |
| **Migration not backward-compatible** | Low | High | Currently all additive. Add the §7.2 guard test before that changes |
| **`use_stub_billing` ships as `True`** | Medium | High | §4.3. Add to the §13.3 checklist and regenerate `.env.example` |
| **Residency check silently disabled** | Medium | High | §4.4. Empty `gcs_location` skips the assertion |
| **Doc↔registry drift** | High | Low | `services/README.md` and `services.yaml` disagree on 6 rows despite `test_registry_matches_readme` being specified. The test does not exist |

### 17.3 `landing-page/` — B6

`landing-page/` is a scraped mirror of **sammylabs.com**, not a Draftly landing
page. `package.json` is named `sammylabs-site-mirror`; `site-mirror/` holds 72
files and ~6.7 MB including that company's `logo_raw.svg`, app icons, OpenGraph
and Twitter share images, marketing copy, and the verbatim text of their terms,
privacy policy, DPA, subprocessors and security pages. `rendered-preview.png`
is a headless-Chrome screenshot of their homepage. All of it is tracked in git.

It is kept deliberately as a **design reference**, which is a normal way to work.
The constraints that follow from that:

- **It is never deployed.** Not to any environment, not behind auth, not as a
  "temporary" placeholder. `serve.mjs` binds `127.0.0.1` and must stay local-only.
- **It is excluded from every build.** It is already orphaned — no
  `pnpm-workspace.yaml` exists, no CI job touches it, nothing references it — so
  the only real risk is a wholesale `rsync` of the repo onto a VM. Deploying from
  an image (§6) removes that risk structurally.
- **Its assets are reference, not source.** The real Draftly landing page needs
  original copy, original artwork, and its own legal pages. Layout and
  interaction ideas are fair to learn from; a logo, a screenshot, and legal
  wording are not things to carry across.
- **Before public launch**, confirm no borrowed asset or wording has reached the
  shipped site. That is a product and legal check, not a technical one.

Two smaller notes: the repo's `CLAUDE.md` privacy rule names Harvey specifically,
so this is outside its literal text but inside its intent, and the directory
carries a `package-lock.json` in a repo that is otherwise pnpm-only
(`packageManager: pnpm@10.23.0`).

### 17.4 Assumptions

Each of these is unverified. If one is wrong, the plan changes.

1. GCP is the target and the project, billing account, and quota exist.
2. `asia-south1` is acceptable for latency **and** for data residency. These are
   different questions with different owners, and the second is part of B1.
3. Neon remains the V0 database and its plan tier's PITR window meets the RPO.
4. A domain is registered with DNS the team controls.
5. Two `e2e-standard-2` VMs are enough. The §9.3 spike test is what confirms it.
6. A GitHub organisation with GHCR access exists for image hosting.
7. Someone is on call. §18 does not currently have a name.
8. Real client data is **not** in scope for this deployment, per B1.
9. The V1 move to self-hosted Postgres is a direction, not a scheduled project.

---

## 18. Deployment sequence and owners

### 18.1 Owners

**Status: Partial.** The repository does not record owners — service docs carry
`Owner:` fields and `backend/docs/services/README.md` §6 names roles
("Conveyancing lawyer", "Legal review", "Ops + legal", "Product", "Engineering")
rather than people. Roles below are therefore what the repo implies; **assign
names before the first deploy.** An unowned rollback at 2am is not a plan.

| Component | Role | Name |
|---|---|---|
| GCP infrastructure, VMs, networking, NAT | Platform / DevOps | *unassigned* |
| Backend API and worker | Backend | *unassigned* |
| Frontend | Frontend | *unassigned* |
| Database, migrations, backups | Backend + Platform | *unassigned* |
| CI/CD | Platform | *unassigned* |
| Secrets and IAM | Platform | *unassigned* |
| Clerk, Gemini, GCS, Resend, PayHere accounts | Ops | *unassigned* |
| **B1 PDPA approvals** | **Legal + practice** | *unassigned* |
| **B2 tenancy key decision** | **Platform team** | *unassigned* |
| Landing page content | Product | *unassigned* |
| On-call | Rotation | *unassigned* |

### 18.2 Sequence

Estimates assume one engineer at a time and exclude waiting on legal.

**Phase 0 — make it buildable (B3). ~1 week.**

| # | Task | Est. | Ref |
|---|---|---|---|
| 1 | Fix CI: run vitest and the full pytest suite; add Postgres service | 1 d | §8.2 |
| 2 | Add `output: "standalone"` to `next.config.ts` | 1 h | §6.2 |
| 3 | Write both Dockerfiles + `.dockerignore`; build locally | 1 d | §6.1 |
| 4 | Add `cors_allowed_origins` to `Settings`; delete the dead comment | 2 h | §4.1 |
| 5 | Regenerate `.env.example` from `Settings`; add the sync contract test | 4 h | §4.3 |
| 6 | Validate `ENVIRONMENT` as a `Literal`; decide where `staging` sits | 2 h | §3.1 |
| 7 | Make `gcs_location` required when storage is `gcs` | 1 h | §4.4 |
| 8 | Write `scripts/smoke.sh` and the migration wrapper | 4 h | §10.3, §7.3 |

**Phase 1 — provision. ~3 days.**

| # | Task | Est. | Ref |
|---|---|---|---|
| 9 | VPC, static IP, Cloud NAT, firewall rules | 4 h | §5.3, §5.4 |
| 10 | Both VMs, reserved internal IPs, Docker, NTP | 4 h | §5.1 |
| 11 | Secret Manager + startup materialisation | 1 d | §4.6 |
| 12 | GCS bucket: UBLA, PAP enforced, **versioning**, region, IAM | 4 h | §12.3, §4.6 |
| 13 | nginx on both VMs; DNS; certbot | 4 h | §5.2 |
| 14 | **Verify the private link before touching DNS** | 1 h | §18.3 |

**Phase 2 — first staging deploy. ~2 days.**

| # | Task | Est. | Ref |
|---|---|---|---|
| 15 | Build, scan, push both images to GHCR | 4 h | §6.4 |
| 16 | Migrate, roll VPS-2, roll VPS-1 | 2 h | §2 |
| 17 | Smoke test and the full §16 checklist | 2 h | §16 |
| 18 | Ops Agent, uptime check, the §11.4 alerts | 1 d | §11.3 |

**Phase 3 — prove it. ~1 week.**

| # | Task | Est. | Ref |
|---|---|---|---|
| 19 | Load tests 1–6 | 2 d | §9.3 |
| 20 | Failover test, both directions, timed | 4 h | §9.4 |
| 21 | Rolling-deploy test under load | 4 h | §9.5 |
| 22 | **First restore drill, timed** | 1 d | §12.4 |
| 23 | Write the results up; confirm or revise the §9.6 targets | 4 h | §9.6 |

**Phase 4 — close the blockers. Unbounded; mostly not engineering time.**

| # | Task | Owner | Ref |
|---|---|---|---|
| 24 | B1 PDPA approvals for all six providers | Legal + practice | §17.1 |
| 25 | B2 tenancy key decision | Platform | §17.1 |
| 26 | B4 implement `--sched` with the advisory lock; fix the per-type lease | Engineering | §1.3 |
| 27 | B7 close the four Critical test findings | Engineering | §9.2 |
| 28 | Rate limiting | Engineering | §13.2 |
| 29 | Populate `tests/conformance/` so L2 becomes reachable | Engineering | §8.2 |
| 30 | Confirm RPO/RTO with the practice | Ops + practice | §12.1 |

**Production is Phase 5 and has no date.** It starts when Phase 4 finishes.

### 18.3 First-deploy runbook

```bash
# ── 0. Prereqs ────────────────────────────────────────────────
gcloud config set project YOUR_PROJECT
gcloud services enable compute.googleapis.com secretmanager.googleapis.com

# ── 1. Network ────────────────────────────────────────────────
gcloud compute networks create draftly-vpc --subnet-mode auto
gcloud compute addresses create draftly-ip --region asia-south1

gcloud compute routers create draftly-router \
  --network draftly-vpc --region asia-south1
gcloud compute routers nats create draftly-nat \
  --router draftly-router --region asia-south1 \
  --nat-all-subnet-ip-ranges --auto-allocate-nat-external-ips

# ── 2. VPS-1 — the edge (public IP, TLS, load balancer) ───────
gcloud compute instances create draftly-edge \
  --zone asia-south1-a --machine-type e2-standard-2 \
  --image-family ubuntu-2404-lts-amd64 --image-project ubuntu-os-cloud \
  --boot-disk-size 50GB --boot-disk-type pd-balanced \
  --network draftly-vpc --private-network-ip 10.128.0.2 \
  --address draftly-ip --tags draftly-edge

# ── 3. VPS-2 — capacity (NO public IP) ────────────────────────
gcloud compute instances create draftly-app \
  --zone asia-south1-c --machine-type e2-standard-2 \
  --image-family ubuntu-2404-lts-amd64 --image-project ubuntu-os-cloud \
  --boot-disk-size 50GB --boot-disk-type pd-balanced \
  --network draftly-vpc --private-network-ip 10.128.0.3 \
  --no-address --tags draftly-app

# ── 4. Firewall — this is what makes the link private ─────────
gcloud compute firewall-rules create allow-https-public \
  --network draftly-vpc --allow tcp:80,tcp:443 \
  --target-tags draftly-edge --source-ranges 0.0.0.0/0

gcloud compute firewall-rules create allow-internal-app \
  --network draftly-vpc --allow tcp:80,tcp:3000,tcp:8000 \
  --target-tags draftly-app --source-ranges 10.128.0.0/20

gcloud compute firewall-rules create allow-ssh-iap \
  --network draftly-vpc --allow tcp:22 \
  --target-tags draftly-edge,draftly-app --source-ranges 35.235.240.0/20

# ── 5. Provision BOTH VMs identically ─────────────────────────
gcloud compute ssh draftly-edge --zone asia-south1-a --tunnel-through-iap
# and: gcloud compute ssh draftly-app --zone asia-south1-c --tunnel-through-iap
  sudo apt update && sudo apt install -y nginx docker.io docker-compose-v2
  sudo timedatectl set-ntp true          # Clerk JWT clock drift — do not skip
  sudo mkdir -p /etc/draftly && sudo chmod 700 /etc/draftly
  # materialise backend.env / frontend.env from Secret Manager, mode 0600
  sudo TAG=$SHA docker compose -f /opt/draftly/compose.yml up -d

# VPS-1 gets the load-balancer nginx (§5.2); VPS-2 gets the thin one.
# VPS-2 additionally runs the worker.

# ── 6. Verify the private link BEFORE touching DNS ────────────
# from VPS-1 — all three must answer, not hang
curl -fsS http://127.0.0.1:8000/health/ready
curl -fsS http://10.128.0.3:8000/health/ready
curl -fsS http://10.128.0.3:3000/ -o /dev/null -w '%{http_code}\n'

# ── 7. Migrations — ONCE, from one place, direct URL ──────────
sudo docker run --rm --env-file /etc/draftly/backend.env \
  ghcr.io/ORG/draftly-api:$SHA uv run alembic upgrade head

# ── 8. DNS + TLS ──────────────────────────────────────────────
# Point the A record at VPS-1's reserved static IP first, then on VPS-1:
sudo certbot --nginx -d draftly.example.lk
sudo systemctl enable certbot.timer

# ── 9. Verify end to end ──────────────────────────────────────
./scripts/smoke.sh https://draftly.example.lk
# then the full §16 checklist
```

**Step 6 is the one people skip and then lose an evening to.** If
`curl http://10.128.0.3:8000/health/ready` from VPS-1 hangs, the cause is the
`allow-internal-app` firewall rule or the app binding to `127.0.0.1` instead of
`0.0.0.0` inside the container. It is not nginx, not DNS, and not TLS.

---

## Appendix — evidence index

Every status claim in this document traces to one of these.

| Claim | Evidence |
|---|---|
| No service above L3; none at L4 | `backend/contracts/services.yaml`; `backend/docs/service-definition-of-done.md` §6 |
| L2 unreachable for every service | `backend/docs/security-model.md` §2.1; `backend/tests/conformance/` contains only `.gitkeep` |
| No build artifacts | No `Dockerfile`, `compose*.yml`, `.dockerignore`, or `*.service` anywhere in the repo |
| Scheduler missing | `backend/src/workers/runner.py` (no `--sched`); no `pg_advisory` in `backend/src/` or `backend/migrations/` |
| Lease is not per-type | `runner.py` `DEFAULT_LEASE_SECONDS = 120` vs `backend/docs/jobs-and-workers.md` §5 |
| `ALLOWED_ORIGINS` does not exist | `backend/src/main.py` — one occurrence repo-wide, in a comment |
| `output: "standalone"` missing | `frontend/next.config.ts` |
| 19 undocumented settings | `backend/src/platform/config.py` vs `backend/.env.example` |
| `use_stub_billing` defaults `True` | `backend/src/platform/config.py` |
| Residency check skippable | `backend/src/bootstrap.py` `_assert_bucket_policy`, guarded by `if expected` |
| `staging` matches neither guard | `backend/src/platform/config.py` `is_production` / `is_non_production` |
| No metrics or tracing | Exhaustive search for `prometheus\|opentelemetry\|otel\|sentry\|statsd\|datadog`; only lockfile transitives |
| Health endpoints correct | `backend/src/main.py` |
| Migrations additive, single head | `backend/migrations/versions/` — 20 files, head `matteragent0001` |
| CI skips 43 of 66 test files | `.github/workflows/ci.yml` vs `[tool.pytest.ini_options].testpaths` |
| DoD CI ≠ actual CI | `backend/docs/service-definition-of-done.md` §8 vs `.github/workflows/ci.yml` |
| PDPA gates closed | `backend/docs/infrastructure.md` |
| Backups never restored | `backend/docs/infrastructure.md`: "A restore that has never been executed is not a backup" |
| No rate limiting | No limiter, middleware, or throttle in `backend/src/`; specified in `backend/docs/api-conventions.md` §8 |
| No security headers | `frontend/next.config.ts` has no `headers()` |
| `landing-page/` is a third-party mirror | `landing-page/package.json` name `sammylabs-site-mirror`; `landing-page/README.md`; `site-mirror/www.sammylabs.com/` |
| Registry ↔ README drift | `backend/docs/services/README.md` §2 vs `backend/contracts/services.yaml` — 6 rows |
