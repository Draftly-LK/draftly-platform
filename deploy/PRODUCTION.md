# Draftly production hosting

Everything about the live deployment at `draftly.adlahiru.com`: where each
piece lives, how a change reaches production, and how to operate it. The
mechanics of the scripts are in [README.md](README.md); this file is the map.

This deployment runs in **demo mode on synthetic data**. See
[Known limitations](#known-limitations-and-approval-gates) before putting real
client material on it.

## What runs where

| Piece | Where | Address |
| --- | --- | --- |
| Landing page and pilot-request form | Docker container `landing` on the VPS | <https://draftly.adlahiru.com> |
| Application (Next.js) | Container `frontend` on the VPS | <https://app.draftly.adlahiru.com> |
| API (FastAPI) and outbox worker | Containers `backend`, `worker`, `migrate` | `https://app.draftly.adlahiru.com/api/*` and `/health/*` |
| Retrieval engine | Container `retrieval`, internal only | `127.0.0.1:8001` on the VPS (SSH tunnel) |
| TLS and routing | Container `caddy` (Let's Encrypt certificates, renewed automatically) | ports 80 and 443 |
| Database | PostgreSQL 18 in container `db` on the VPS (volume `draftly_pg-data`) | internal only: `db:5432` on the compose network, never published |
| Sign-in | Clerk (development instance `popular-lark-48`) | Clerk dashboard |
| Source, CI and CD | GitHub `Draftly-LK/draftly-platform` | Actions tab |

The app and the API share one origin (`app.draftly.adlahiru.com`), so the
browser makes no cross-origin calls. The retrieval engine has no login and is
never routed by Caddy; do not add a `ports:` entry for it.

## DNS

Records live at the registrar (Porkbun). Only the two below concern Draftly;
leave every other record (the apex `adlahiru.com` GitHub Pages addresses, `www`,
MX, SPF, Google verification, `_acme-challenge`) alone.

| Type | Host | Value | Serves |
| --- | --- | --- | --- |
| A | `draftly.adlahiru.com` | `13.140.183.52` | landing page |
| A | `app.draftly.adlahiru.com` | `13.140.183.52` | application and API |

Caddy needs both names to resolve to the server before it can obtain a
certificate for them. If `app.` was added after the first deploy, run
`docker restart draftly-caddy-1` on the server to retry immediately.

## The server

Ubuntu 24.04, 4 vCPU, 8 GB RAM, 2 GB swap, public address `13.140.183.52`.

| What | Where |
| --- | --- |
| Repository clone (what production runs) | `/home/deploy/draftly-platform`, owned by the `deploy` user |
| All runtime secrets | `/home/deploy/draftly-platform/deploy/.env` (mode 600, git-ignored) |
| Research inputs for retrieval | `/home/deploy/draftly-platform/deploy/.research` (sparse clone, git-ignored) |
| GitHub access for the server | `/home/deploy/.ssh/`: `github_deploy` (platform repo) and `draftly_research_deploy` (research repo, read-only), selected through `~/.ssh/config` |
| CI login | `/home/deploy/.ssh/authorized_keys`, one key pinned to a forced command |
| Forced-command script (root-owned copy of `deploy/ci-deploy.sh`) | `/usr/local/bin/draftly-ci-deploy` |
| Persistent data | Docker volumes `draftly_pg-data` (the database), `draftly_pilot-requests`, `draftly_source-files`, `draftly_caddy-data` (certificates) |
| Nightly backups (03:15) | `/var/backups/draftly`: database dump (`database-*.dump`) and volume archives, last 14 of each, from `/etc/cron.d/draftly-backup`. `neon-final-*.dump` is the last copy taken from Neon before the move |
| Deploy logs | `/var/log/draftly/` and `deploy/vps.sh logs` |

Hardening in place: `ufw` denies everything inbound except 22, 80 and 443;
`fail2ban` guards SSH; unattended security updates are on; containers run as
non-root users with memory limits; Caddy sends HSTS and the usual security
headers. `deploy/vps.sh setup` reproduces all of it on a fresh machine.

Not changed, because it could lock you out: SSH still accepts passwords and
root login. Once you log in with a key, set `PasswordAuthentication no` and
`PermitRootLogin prohibit-password` in `/etc/ssh/sshd_config.d/`.

## Branches and how a change reaches production

```text
dev/<name>/<topic>  --PR-->  main  --PR-->  prod  --push triggers-->  CI -> deploy -> smoke test
```

- `main` is the integration branch. Nothing is committed or pushed to it
  directly; changes arrive by pull request.
- `prod` is the **deployment branch**. Every push to `prod` runs
  `.github/workflows/deploy.yml`. Promote by opening a pull request from `main`
  into `prod` (or a hotfix branch into `prod`).
- Deploy sequence on each push to `prod`:
  1. `ci.yml` runs (frontend typecheck, lint, tests, build; backend lock, ruff,
     mypy, pytest; landing tests; Docker image builds; compose, Caddyfile and
     shell script validation; markdown lint). A red CI stops the deploy.
  2. The workflow SSHes to the server as `deploy`. The key can only run
     `deploy/ci-deploy.sh`, which fast-forwards the clone to the exact commit
     that passed CI and runs `deploy/vps.sh deploy`.
  3. `vps.sh deploy` refreshes the research inputs, builds the four images on
     the server, runs Alembic migrations, starts the stack and health-checks it.
     If any step fails, the previous images are put back automatically.
  4. The workflow smoke-tests the public URLs. If that fails, it rolls back.
- Manual runs: Actions, Deploy, "Run workflow" on branch `prod`, then choose
  `deploy` (redeploy the tip of `prod`) or `rollback`.

## One-time GitHub setup

These live in GitHub, not in the repository, so they cannot be scripted from
here. Repository Settings, then:

1. **Secrets and variables, Actions, secrets.** Add:

   | Secret | Value |
   | --- | --- |
   | `VPS_HOST` | `13.140.183.52` |
   | `VPS_USER` | `deploy` |
   | `VPS_SSH_KEY` | private key from `/root/draftly-github-actions-key` on the server |
   | `VPS_KNOWN_HOSTS` | the line in `/root/draftly-vps-known-hosts` on the server |
   | `VPS_PORT` | optional; only if SSH is not on 22 |

   Read the two files on the server yourself (`cat`), paste them into GitHub,
   then delete them: `shred -u /root/draftly-github-actions-key`. Application
   secrets (Clerk, database, Gemini) are **not** stored in GitHub; they stay in
   `deploy/.env` on the server.
2. **Environments.** Create `production`. Optionally add required reviewers so
   each deploy needs an approval click.
3. **Branch protection** (Settings, Branches) for both `main` and `prod`:
   require a pull request, require the status checks `verify`, `backend`,
   `landing`, `images (backend)`, `images (frontend)`, `images (landing-page)`
   and `deploy-config`, and block force pushes. GitHub protection is not
   reliable on this private organisation repository, so agents also follow the
   no-direct-push rule in `CLAUDE.md`.
4. **Variables** (optional): `APP_URL` and `LANDING_URL` if the hostnames change.

## Secrets: what exists and where

| Secret | Lives in | Rotate at |
| --- | --- | --- |
| `CLERK_SECRET_KEY`, publishable key | `deploy/.env` | Clerk dashboard, API keys |
| `POSTGRES_PASSWORD`, `DATABASE_URL`, `DATABASE_URL_DIRECT` | `deploy/.env` (generated on the server) | `ALTER USER draftly PASSWORD '...'` in the `db` container, then update all three lines and redeploy |
| `GEMINI_API_KEY` | `deploy/.env` | Google AI Studio |
| `PARTY_IDENTIFIER_KEY`, `PARTY_BLIND_INDEX_KEY`, `API_CURSOR_SIGNING_KEY` | `deploy/.env` (generated on the server) | **Do not rotate casually.** The first two encrypt and index stored party identifiers; changing them makes existing rows unreadable. Back them up in your password manager |
| CI SSH key | GitHub secret `VPS_SSH_KEY` and `authorized_keys` | Generate a new pair, replace both |
| Research repo deploy key | `/home/deploy/.ssh/draftly_research_deploy`, GitHub repo Deploy keys | Replace both |

After changing anything in `deploy/.env`, apply it with
`deploy/vps.sh deploy` (a change to `DOMAIN` or the Clerk publishable key needs
`deploy/vps.sh deploy frontend` because `NEXT_PUBLIC_*` values are compiled in).

The Neon URLs, Clerk secret and Gemini key were shared in a chat while setting
this up. Treat them as exposed: rotate the Clerk and Gemini keys, update
`deploy/.env` and redeploy. The Neon database is no longer used, so delete that
project (or reset its password) once you are happy with the move, then remove
the `LEGACY_NEON_*` lines from `deploy/.env`. The Cloudflare R2 keys and the GCP service-account file in the local
`.env` files are not used by this deployment: the current backend no longer
reads `OBJECT_STORAGE_*`, and Document AI is off in demo mode.

## Clerk settings

In the Clerk dashboard for the development instance, allow
`https://app.draftly.adlahiru.com` as an origin. The backend accepts session
tokens only from that origin (`CLERK_AUTHORIZED_PARTY`). Moving to a Clerk
production instance needs DNS records on the domain and new keys in
`deploy/.env`, then `deploy/vps.sh deploy frontend`.

## Operating it

Run on the server as the `deploy` user, from `~/draftly-platform`:

| Task | Command |
| --- | --- |
| Health, memory, containers | `deploy/vps.sh status` |
| Follow logs (all, or one service) | `deploy/vps.sh logs` / `deploy/vps.sh logs backend` |
| Redeploy after a manual edit | `deploy/vps.sh deploy` |
| Roll back to the previous release | `deploy/vps.sh rollback` (or the workflow's `rollback`) |
| Backup volumes now | `deploy/vps.sh backup` |
| Stop everything (data kept) | `deploy/vps.sh down` |
| Read pilot requests | `docker run --rm -v draftly_pilot-requests:/d alpine sh -c 'cat /d/*.json'` |
| Give an account a plan by hand (a trial starts on its own at sign-in) | `deploy/vps.sh grant-trial --user usr_... --days N` (see below) |
| Reach retrieval | `ssh -L 8001:127.0.0.1:8001 deploy@13.140.183.52`, then `curl http://127.0.0.1:8001/health` |

A rollback restores the previous images only. Alembic migrations are
forward-only and are not reverted, so write migrations that the previous
release can still run against (add columns before using them, drop them a
release later).

Restore a volume backup with
`docker run --rm -v draftly_pilot-requests:/d -v /var/backups/draftly:/b alpine tar -xzf /b/<file>.tar.gz -C /d`.

Restore the database from a dump (this replaces its contents, so stop the API
first):

```bash
cd ~/draftly-platform/deploy
docker compose --project-name draftly --env-file .env -f docker-compose.vps.yml --profile web stop backend worker
docker exec -i draftly-db-1 pg_restore -U draftly -d draftly --clean --if-exists --no-owner --no-acl \
  < /var/backups/draftly/database-<timestamp>.dump
cd .. && deploy/vps.sh deploy backend
```

The backups sit on the same server as the database, so copy them somewhere
else too (another machine, or object storage). A disk failure would take both.

To go back to Neon, put the two `LEGACY_NEON_DATABASE_URL*` values back into
`DATABASE_URL` and `DATABASE_URL_DIRECT` and run `deploy/vps.sh deploy backend`.
Anything written since the move exists only in the local database.

## Accounts, plans and gated features

Features are gated by plan: legal research, drafting, export and document
processing, plus quotas such as active matters and pages per month.
`ENFORCE_PLAN_LIMITS=true` (the code default, and this server's setting) means
a gated call is checked against the account's plan.

**How an account gets a plan: an automatic trial, not an admin step.**
`POST /me/provision` — called on every sign-in — grants an active account a
30-day trial (`SIGNUP_TRIAL_DAYS`, seeded plan `plan_trial_v1`) the first time
it has no subscription yet (`BillingService.ensure_trial`). This is what fixed
"asking a legal question shows an error" for pilot accounts created earlier:
their next sign-in grants the trial with no admin step. It is idempotent — an
account with a subscription already (trial, paid, or restricted) is untouched
— and a race between two first requests for the same brand-new account is
resolved by the database's own `uq_subscription_user` constraint, not a lost
update. Set `SIGNUP_TRIAL_DAYS=0` to turn auto-granting off.

`ENFORCE_PLAN_LIMITS=false` is a break-glass switch (every account gets every
feature, no quota, whatever its plan or lack of one) for an emergency where the
trial plan itself is misconfigured. It is off on this server and should stay
off — the trial above is the intended way in. The backend logs
`startup.plan_limits_disabled` at boot as a reminder if it is ever turned on.

To grant a plan by hand instead (a longer trial, a different plan, or an
account you want on a plan without waiting for its next sign-in):

1. Put the staff user id(s) in `PLATFORM_ADMIN_USER_IDS` in `deploy/.env` (a
   comma-separated list of `usr_...` ids) and run `deploy/vps.sh deploy backend`.
   Empty means no one can grant.
2. Find the account's user id. Denied calls name it in the backend log:
   `deploy/vps.sh logs backend | grep feature_denied`.
3. Run `deploy/vps.sh grant-trial --user usr_... --days 30`. The trial length is
   required because it is a billing decision, not a default. It uses the
   seeded `plan_trial_v1` plan unless `--plan` names another active plan.

The tool calls the billing service's own `grant_trial`, so the admin check, the
"account must be active" and "no existing subscription" rules and the audit
event (`billing.subscription.trial_granted`, with the admin as actor) all
apply — the same rules `ensure_trial` follows for the automatic case, recorded
instead as `billing.subscription.trial_self_started`. The manual grant is also
available over HTTP as `POST /api/v1/admin/subscriptions/{userId}/grant-trial`.

## No demo data

The frontend still contains fixture data for the offline demo and tests. That
data is shown only when `NEXT_PUBLIC_API_BASE_URL` is unset. Production builds
set it, and then the app shows what the database returns, or nothing: no
fixture matters, documents, facts, checks, drafts, audit events, deadlines or
palette entries, and the browser's old demo state is deleted rather than loaded.
Form templates, question sets and workflow definitions are product catalogue,
not case data, and are still shown.

## Known limitations and approval gates

- **Gemini approval (`PROVIDER_DATA_APPROVAL=true`).** The owner approved
  sending typed research questions and statute text to Google's Gemini API on
  2026-09-21, so `deploy/.env` sets this flag and legal research produces
  grounded answers. Without it the research composer is not built and every
  question returns "insufficient authority". The flag is also the gate that lets
  non-synthetic documents reach a provider, but `EXTRACTION_PROVIDER` is still
  `stub`, so no document is sent to a provider yet. Record provider region,
  retention and training terms before switching extraction to Gemini.
- **Database on the same server.** The database moved from Neon (Singapore)
  to PostgreSQL on this VPS on 2026-09-21, which took API calls from 1.5 to 5
  seconds down to tens of milliseconds. The trade-off is that the server and its
  disk are now one failure domain: keep off-server copies of
  `/var/backups/draftly`.
- **Demo mode.** The backend runs with `ENVIRONMENT=local` because outside
  `local`, `test` and `ci` it demands approved production providers: GCS
  evidence storage with `DRAFTLY_STORAGE_REAL_DATA_APPROVED`, an approved
  extraction provider and the real matter-access adapter. Those are open
  decisions in `backend/backend-implementation-plan-v0.md` for the team to
  approve; this deployment does not choose them. Use synthetic data only.
- **Not shared with development.** The local database holds a copy of what
  was in the old shared development database at the time of the move (73
  tables, 937 rows). Remove any test accounts you do not want before real use.
- **One API worker process.** Demo-mode adapters keep state in memory, so the
  API runs a single uvicorn worker. Scale up only after production adapters
  replace them.
- **Retrieval quality is unchanged, only its source.** The research API now
  calls the retrieval container (`RETRIEVAL_BASE_URL`,
  `HttpStatuteRetrievalAdapter`) instead of the corpus bundled into the
  backend image, so the two stop drifting apart. This is not the same as the
  fuller "three-channel hybrid" engine described in the research repo's
  design docs: the deployed index is BM25-lexical only
  (`RETRIEVAL_WITH_EMBEDDINGS=0`), the same technique the old bundled corpus
  used, so a question that missed a matching statute before can still miss it
  now. Set `RETRIEVAL_WITH_EMBEDDINGS=1` and rebuild the retrieval image to
  add the dense channel (spends Gemini credits at build time). If the
  retrieval container is unreachable, search degrades to no passages —
  answers become "insufficient authority," not an error.
- **Single server.** One VPS is a single point of failure. Restoring from
  nothing takes `vps.sh setup`, `init`, a filled `deploy/.env` and
  `vps.sh deploy`.
