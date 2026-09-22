# Hosting and migrating Draftly

Written for whoever hosts this next — a person, or a Claude Code agent handed
this file with an instruction like "host this on a new VPS" or "migrate the
deployment to this new server." It is the procedure. Two other files hold the
supporting detail and are linked from here rather than repeated:

- [`deploy/PRODUCTION.md`](deploy/PRODUCTION.md) — the live server as it is
  today: exact hostnames, what runs where, every secret and where it lives,
  the CI/CD pipeline, day-to-day operating commands, known limitations.
- [`deploy/README.md`](deploy/README.md) — what each script and compose file
  does, and the alternative hosting shapes (`WEB_ON_VPS=0`, images built
  elsewhere) this deployment does not use.

If you are an agent starting this cold: read this file fully before running
anything. It names every value you need and where each one comes from (a
person, an existing server, or a value you generate). Where a step needs the
person's input — DNS access, a Clerk account, a Gemini key — stop and ask for
it rather than guessing or inventing a placeholder that quietly ships broken.

## What you are hosting

One repository, four things deployed together on one VPS behind one Caddy:

| Piece | Source | Public? |
| --- | --- | --- |
| Landing page (pilot-request intake) | `landing-page/` | Yes |
| Application (Next.js) | `frontend/` | Yes |
| API + outbox worker (FastAPI) | `backend/` | Yes (`/api/*`, `/health/*`) |
| Retrieval engine (statute/case-law search) | private `draftly-research` repo, built into an image by `deploy/retrieval/Dockerfile` | No — internal only, no auth. Never give it a `ports:` entry |
| Database | bundled PostgreSQL, same VPS | No |

The app and the API share one origin (no CORS to configure). The mechanism
that puts all of this on the VPS is `deploy/vps.sh` with `WEB_ON_VPS=1`; see
`deploy/README.md` if a different shape (frontend on Vercel, images built off
the server) is ever wanted instead — this deployment does not use that path.

## Before you start: what only a person can give you

Collect these before running anything; there is no safe default for any of
them.

1. **A VPS.** Ubuntu or Debian, reachable over SSH as root or a sudo user.
   This deployment runs comfortably on 4 vCPU / 8 GB RAM (the Next.js build
   and the retrieval index build are the memory-heavy steps); 2 GB RAM works
   for the API-only shape in `deploy/README.md` but not this one.
2. **Two DNS records**, both A records at the new server's IP: one for the
   landing page (e.g. `draftly.example.com`) and one for the app
   (`app.draftly.example.com`). Caddy cannot get a certificate for either
   until it resolves — confirm with `dig +short <name>` before deploying.
3. **Read access to the private `draftly-research` repository.** Either an
   SSH deploy key you generate and the person adds to that repo (read-only;
   see step 4 below), or a fine-grained GitHub token with read-only Contents
   access, set as `RESEARCH_REPO_URL=https://<token>@github.com/<org>/draftly-research.git`
   in `deploy/.env`.
4. **Clerk keys** for sign-in: a publishable key (`pk_...`) and a secret key
   (`sk_...`). A development instance is fine for a pilot; a production
   instance needs its own DNS records on the domain, set up separately.
5. **A Gemini API key**, if grounded research answers should work (not just
   search). Ask before turning this on: it means the person's typed research
   questions and the matching statute passages are sent to Google's Gemini
   API. See `deploy/PRODUCTION.md`, "Gemini approval," for how this was
   recorded when it was approved for the current server.
6. **Whether this is a fresh install or a migration carrying real data.** A
   fresh install needs nothing else. A migration additionally needs the old
   server's `deploy/.env` (or at minimum the four keys called out in
   [Migrating with existing data](#migrating-an-existing-deployment-to-a-new-vps)
   below) and a current backup.
7. **GitHub repository access** to add Actions secrets, if continuous
   deployment should also move to the new server (recommended — do this in
   the same session, not "later").

## Fresh install on a new VPS

Run as root (or with sudo) on the new server, from a clone of this
repository:

```bash
git clone git@github.com:<org>/draftly-platform.git
cd draftly-platform
sudo deploy/vps.sh setup      # Docker, swap, ufw, fail2ban, unattended-upgrades, backup cron
```

Then create a dedicated, low-privilege `deploy` user for everything else —
never run the application as root:

```bash
id deploy >/dev/null 2>&1 || useradd --create-home --shell /bin/bash --groups docker deploy
install -d -m 700 -o deploy -g deploy /home/deploy/.ssh
```

Give that user its own SSH identity for the platform repo, and a second,
read-only one for the private research repo (never reuse a person's own key on
a server):

```bash
sudo -u deploy ssh-keygen -t ed25519 -N '' -f /home/deploy/.ssh/github_deploy -C vps-deploy
sudo -u deploy ssh-keygen -t ed25519 -N '' -f /home/deploy/.ssh/draftly_research_deploy -C draftly-research-deploy
```

Print both `.pub` files and stop here: the platform-repo key needs write
access added as that account's own SSH key (or a machine user with push
access) so it can clone; the research-repo key needs to be added as a
**read-only Deploy key** on the `draftly-research` repository's GitHub
settings. Wait for the person to confirm both before continuing.

Point the `deploy` user's SSH at the right key for each host, and pin GitHub's
host key (never trust whatever answers on first connect — verify the printed
fingerprint against GitHub's published one):

```bash
sudo -u deploy tee /home/deploy/.ssh/config <<'EOF'
Host github.com
  HostName github.com
  User git
  IdentityFile ~/.ssh/github_deploy
  IdentitiesOnly yes

Host github-research
  HostName github.com
  User git
  IdentityFile ~/.ssh/draftly_research_deploy
  IdentitiesOnly yes
EOF
ssh-keyscan -t ed25519 github.com > /tmp/gh.key
ssh-keygen -lf /tmp/gh.key   # compare to SHA256:+DiY3wvvV6TuJJhbpZisF/zLDA0zPMSvHdkr4UvCOqU
install -m 600 -o deploy -g deploy /tmp/gh.key /home/deploy/.ssh/known_hosts
```

Clone the platform repo as `deploy` (this becomes the running copy), and
write `deploy/.env`:

```bash
sudo -u deploy bash -c 'cd ~ && git clone git@github.com:<org>/draftly-platform.git'
cd /home/deploy/draftly-platform/deploy
sudo -u deploy bash -c 'WEB_ON_VPS=1 ./vps.sh init'
```

`init` writes `deploy/.env` from `.env.example`, fills in `DOMAIN`,
`LANDING_DOMAIN` (defaulting to `<ip>.sslip.io` names if you have not put the
real hostnames in yet — replace them with the two DNS names from step 2
above), a bundled-Postgres `DATABASE_URL`, and generates
`PARTY_IDENTIFIER_KEY`, `PARTY_BLIND_INDEX_KEY`, `API_CURSOR_SIGNING_KEY`.
**On a fresh install let it generate these three; on a migration, overwrite
them with the old server's values instead — see below, this is the one step
that must not be skipped or those existing encrypted fields become
unreadable.** Then edit `deploy/.env` (`chmod 600` already applied) and set:

```bash
DOMAIN=app.draftly.example.com
LANDING_DOMAIN=draftly.example.com
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_...
CLERK_SECRET_KEY=sk_...
GEMINI_API_KEY=...            # optional — see "Before you start", item 5
PLATFORM_ADMIN_USER_IDS=      # Draftly staff usr_... ids; optional, see PRODUCTION.md
```

Everything else in `deploy/.env` has a working default. Then deploy:

```bash
deploy/vps.sh deploy
```

This fetches the retrieval corpus from the research repo, builds the four
images, runs migrations, starts the stack, and checks it end to end
(`backend`, `retrieval`, `frontend`, `landing`, the certificate). If any step
fails, it rolls the images back automatically and tells you what to check —
read the failure before retrying; do not just re-run blindly.

Read `deploy/PRODUCTION.md`, "One-time GitHub setup," to add a `deploy` user
in the `docker` group, the CI SSH key restricted to
`/usr/local/bin/draftly-ci-deploy`, and the four repository secrets
(`VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`, `VPS_KNOWN_HOSTS`) so that pushing to
`prod` deploys here automatically from then on.

Finally, in the Clerk dashboard, add `https://<DOMAIN>` (the app hostname, not
the landing one) as an allowed origin for that Clerk instance.

## Migrating an existing deployment to a new VPS

This is a fresh install (above) plus carrying the existing state across. Do
the fresh install through `vps.sh init`, then stop before `deploy/vps.sh
deploy` and do the following instead.

### 1. Copy the secrets that must not be regenerated

From the **old** server's `deploy/.env`, copy these four values into the
**new** server's `deploy/.env`, overwriting whatever `init` generated:

| Key | Why it must travel, not regenerate |
| --- | --- |
| `PARTY_IDENTIFIER_KEY` | Encrypts stored party identifiers. A new key makes every existing encrypted value unreadable, permanently. |
| `PARTY_BLIND_INDEX_KEY` | Indexes those same encrypted fields for lookup. Same failure mode as above. |
| `API_CURSOR_SIGNING_KEY` | Signs pagination cursors. A mismatch just breaks in-flight pagination, not stored data — lower stakes, but still copy it. |
| `POSTGRES_PASSWORD` | Only matters if you are also restoring the bundled database (next step) into a fresh container with this same password baked into the restored dump's connection assumptions. If you are pointing at a still-running external database instead, copy `DATABASE_URL`/`DATABASE_URL_DIRECT` verbatim instead of this. |

Also carry over anything the person cares about keeping identical: the Clerk
keys (same Clerk instance, unless deliberately moving to a new one), the
Gemini key, `PLATFORM_ADMIN_USER_IDS`.

### 2. Move the database

The old server's nightly backup already has what you need
(`deploy/PRODUCTION.md`, "Nightly backups"): a `pg_dump` custom-format file at
`/var/backups/draftly/database-<timestamp>.dump` on the **old** server. Take a
fresh one now rather than trusting last night's:

```bash
# on the OLD server
cd ~/draftly-platform && deploy/vps.sh backup
```

Copy that file to the new server (`scp`), then, on the **new** server, with
the stack not yet started:

```bash
cd ~/draftly-platform/deploy
docker compose --project-name draftly --env-file .env -f docker-compose.vps.yml --profile localdb up -d db
# wait for it healthy: docker ps
docker exec -i draftly-db-1 pg_restore -U draftly -d draftly --no-owner --no-acl < database-<timestamp>.dump
```

If the old deployment used a managed database instead of the bundled one
(check `DATABASE_URL` — the bundled one always points at `db:5432`), skip the
restore and instead paste the same `DATABASE_URL` / `DATABASE_URL_DIRECT` into
the new server's `deploy/.env`; nothing to copy, the database has not moved.

### 3. Move what is not in the database

Two Docker volumes hold data outside Postgres: `draftly_pilot-requests`
(pilot-request emails) and `draftly_source-files` (uploaded evidence). Copy
each the same way:

```bash
# on the OLD server: archive
docker run --rm -v draftly_pilot-requests:/d -v /tmp:/out alpine tar -czf /out/pilot-requests.tar.gz -C /d .
# scp /tmp/pilot-requests.tar.gz to the new server, then, on the NEW server:
docker run --rm -v draftly_pilot-requests:/d -v /tmp:/in alpine tar -xzf /in/pilot-requests.tar.gz -C /d
```

Repeat for `draftly_source-files`. Do this before the first `deploy/vps.sh
deploy` on the new server, or after — the volumes persist independently of the
running containers either way, but restoring before the first deploy means
the very first health check sees the real data.

### 4. Deploy, verify, then decommission the old server

```bash
deploy/vps.sh deploy
```

Verify against the **new** server's own hostnames (not the old one) before
touching DNS:

```bash
curl -sk --resolve <app-domain>:443:<new-ip> https://<app-domain>/health/ready
curl -sk --resolve <landing-domain>:443:<new-ip> https://<landing-domain>/
```

Only then repoint the two DNS records (`deploy/PRODUCTION.md`, "DNS") at the
new server's IP, and re-run the two `curl` checks without `--resolve` once DNS
has propagated, to confirm the public path matches. Update the four GitHub
Actions secrets (`VPS_HOST` especially) so `git push` to `prod` deploys to the
new server from then on, not the old one.

Keep the old server running, unreachable from its old DNS name but still up,
for a day or two before decommissioning it — it is the fallback if something
about the new server surfaces only under real traffic. When you are ready to
decommission it: take one last backup, confirm it copied off that server, then
stop it (`deploy/vps.sh down`) or destroy the VPS through its provider.

## After either path

Update `deploy/PRODUCTION.md` — it describes one specific server, so its IP,
DNS names, secret rotation notes, and "known limitations" section need to
match the server you just stood up, not the one this file was last written
against. That file, not this one, is where the current server's specifics
belong.
