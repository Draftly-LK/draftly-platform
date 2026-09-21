# Deploying Draftly with Docker

This folder runs the whole application on one small VPS (sized for 1 GB RAM):

| Service | Image built from | Notes |
| --- | --- | --- |
| `caddy` | `caddy:2.10-alpine` | HTTPS and routing. `/api/*` and `/health/*` go to the backend, everything else to the frontend. |
| `frontend` | `frontend/Dockerfile` | Next.js standalone server. |
| `backend` | `backend/Dockerfile` | FastAPI. Uploaded source files live in the `source-files` volume. |
| `migrate` | same image as `backend` | Runs `alembic upgrade head` once per `up`, then exits. The backend waits for it. |
| `worker` | same image as `backend` | Outbox worker. Off by default; enable with `--profile worker`. |
| `retrieval` | `deploy/retrieval/Dockerfile` (code and corpus from the research repo) | Statute and case-law search. Internal network only. |

Postgres is not in the base stack. Use the managed Neon database: the pooled URL
in `DATABASE_URL` and the direct URL in `DATABASE_URL_DIRECT`. The Vercel + VPS
path below can run a bundled Postgres instead.

There are two ways to host it:

- **Vercel + VPS** (`vps.sh`): the Next.js frontend on Vercel, everything
  else on the VPS, built there from a clone of this repository. Meant for a
  temporary demo on synthetic data. Described in the next section.
- **Everything on the VPS, images built elsewhere** (`docker-compose.yml`,
  `build.sh`, `ship.sh`): one origin behind one Caddy. The rest of this README
  after the next section describes it.

## Vercel + VPS (temporary demo)

| Where | What |
| --- | --- |
| Vercel | Next.js frontend (`frontend/`) |
| VPS | `docker-compose.vps.yml`: Caddy (API domain only), migrations, backend, outbox worker, retrieval, and a bundled Postgres unless you use Neon |

The browser loads the site from Vercel and calls the API on the VPS
cross-origin. The backend allows exactly one browser origin, `FRONTEND_ORIGIN`
(passed to it as `ALLOWED_ORIGINS`), and Clerk accepts tokens only from that
origin (`CLERK_AUTHORIZED_PARTY`). Use one fixed Vercel URL, such as the
production `*.vercel.app` address or your own domain. Per-commit preview URLs
change every time and will be refused.

Measured idle use of the VPS stack: about 240 MB in total. Only the backend
and retrieval images are built on the server, so 2 GB of swap is plenty.

### 1. VPS

On a fresh Ubuntu or Debian VPS (1 GB RAM, about 5 GB free disk):

```bash
git clone https://github.com/Draftly-LK/draftly-platform.git
cd draftly-platform
sudo deploy/vps.sh setup     # Docker, 2 GB swap, ufw rules; log out and back in afterwards
deploy/vps.sh init           # writes deploy/.env with generated secrets
nano deploy/.env             # FRONTEND_ORIGIN, Clerk keys, optionally GEMINI_API_KEY
deploy/vps.sh deploy         # fetch retrieval inputs, build, start, check
```

What `init` sets up, all editable in `deploy/.env`:

- `DOMAIN` is the API's hostname. It defaults to `<ip-with-dashes>.sslip.io`,
  which resolves to the server's IP, so Caddy gets a real certificate without
  a domain. Put your own (sub)domain there if you have one.
- With no `DATABASE_URL`, a bundled Postgres 16 container (profile `localdb`)
  keeps the data in the `pg-data` volume. Paste Neon URLs instead to use Neon.
- `ENVIRONMENT=local`. The backend only starts its local adapters (disk
  evidence store, stub extraction, stub matter access for parties) in
  `local`, `test` or `ci`; with `production` those parts of the app fail.
  So this deployment is for synthetic data only. Sign-in is still real:
  the stack refuses to start without Clerk settings, and never enables the
  stub identity.
- Party encryption, blind-index and cursor keys are generated.

You fill in:

- `FRONTEND_ORIGIN`: the Vercel URL, for example
  `https://draftly-demo.vercel.app` (no trailing slash, no path).
- `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` and `CLERK_SECRET_KEY` from a Clerk
  **development** instance (`pk_test_…`, `sk_test_…`). A production Clerk
  instance needs DNS records on a domain you own. `CLERK_ISSUER` is worked out
  from the publishable key and `CLERK_AUTHORIZED_PARTY` from `FRONTEND_ORIGIN`.

`deploy` finishes by checking the API's readiness, the retrieval engine, and
that a CORS preflight from `FRONTEND_ORIGIN` is allowed.

The research repository is private. `deploy` clones it into `deploy/.research`
(git-ignored) as a shallow, sparse checkout of only the files the retrieval
image copies (the allowlist in `retrieval/Dockerfile.dockerignore`, about 1 GB),
using the same GitHub access this clone used. If that fails, set
`RESEARCH_REPO_URL=https://<token>@github.com/Draftly-LK/draftly-research.git` in
`deploy/.env` with a read-only fine-grained token.

### 2. Vercel

Import the repository in Vercel, then in the project settings:

| Setting | Value |
| --- | --- |
| Root Directory | `frontend` |
| Framework Preset | Next.js |
| Install / build command | defaults (pnpm is picked up from the lockfile) |
| Node.js version | 22.x |

Environment variables (Production):

| Name | Value |
| --- | --- |
| `NEXT_PUBLIC_API_BASE_URL` | `https://<DOMAIN from deploy/.env>` (bare origin, no `/api/v1`) |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | same `pk_test_…` as on the VPS |
| `CLERK_SECRET_KEY` | same `sk_test_…` as on the VPS |
| `NEXT_PUBLIC_CLERK_SIGN_IN_URL` | `/sign-in` |
| `NEXT_PUBLIC_CLERK_SIGN_UP_URL` | `/sign-up` |
| `NEXT_PUBLIC_CLERK_AFTER_SIGN_OUT_URL` | `/sign-in` |
| `NEXT_PUBLIC_USE_MOCK_PIPELINE` | `false` |
| `MULTILINGUAL_LANGUAGE_SUPPORT` | `true` |

Do not set `AUTH_BYPASS`. `NEXT_PUBLIC_*` values are baked in at build time, so
redeploy on Vercel after changing them. `frontend/vercel.json` turns off
deploys on every Git push, so deploy with `vercel --prod` from `frontend/` or
with "Redeploy" in the dashboard.

If the Vercel URL changes, update `FRONTEND_ORIGIN` (and
`CLERK_AUTHORIZED_PARTY` if you set it by hand) in `deploy/.env` and run
`deploy/vps.sh deploy` again.

## Everything on one VPS (frontend, landing page, backend, retrieval)

`WEB_ON_VPS=1` moves the frontend off Vercel and adds the landing page, all
built on the server from this repository. Sized for 4 vCPU / 8 GB RAM: the
Next.js build peaks at a few GB, which is fine there but not on a 1 GB box. A
bundled Postgres is used unless you paste Neon URLs.

| Hostname | Served by |
| --- | --- |
| `DOMAIN` | `/api/*` and `/health/*` to the backend, everything else to the Next.js frontend. One origin, so no CORS. |
| `LANDING_DOMAIN` | The landing page and its pilot-request form. `/app` on it redirects to `https://DOMAIN/`. |

The retrieval engine stays internal (no route in Caddy), as before.

```bash
git clone https://github.com/Draftly-LK/draftly-platform.git
cd draftly-platform
sudo deploy/vps.sh setup                 # once; log out and back in afterwards
WEB_ON_VPS=1 deploy/vps.sh init          # writes deploy/.env; sets LANDING_DOMAIN
nano deploy/.env                         # Clerk keys, optionally GEMINI_API_KEY
deploy/vps.sh deploy                     # research inputs, build 4 images, start, check
```

Both hostnames must resolve to the server before the first `deploy`. Without a
domain, `init` uses `<ip-with-dashes>.sslip.io` for the app and
`landing.<ip-with-dashes>.sslip.io` for the landing page. For a real domain,
create two A records and put them in `DOMAIN` and `LANDING_DOMAIN`. Changing
`DOMAIN` or the Clerk publishable key means rebuilding the frontend
(`deploy/vps.sh deploy frontend`), because `NEXT_PUBLIC_*` values are inlined at
build time.

In the Clerk dashboard, add `https://<DOMAIN>` as an allowed origin. The
backend accepts tokens only from that origin (`CLERK_AUTHORIZED_PARTY`,
derived from `DOMAIN`).

The landing page keeps the pilot-request emails in the `pilot-requests` Docker
volume (`/data/pilot-requests` in the container). That volume is not served
anywhere. Read it with:

```bash
docker run --rm -v draftly_pilot-requests:/d alpine sh -c 'cat /d/*.json'
```

Back it up if you care about those leads; `deploy/vps.sh down` keeps it.

### Continuous delivery

`.github/workflows/deploy.yml` deploys to the VPS after CI passes on `main`,
and can be run by hand from the Actions tab. It logs in over SSH, fast-forwards
the server's clone to `origin/main` and runs `deploy/vps.sh deploy`. The job
fails if the build, a migration or a health check fails.

One-time setup:

1. On the server, create the clone once (the steps above) as the user that will
   deploy. That user must be in the `docker` group, which is root-equivalent, so
   use a dedicated user and a key that only does this.
2. On your machine: `ssh-keygen -t ed25519 -f draftly-deploy -N ''`. Append
   `draftly-deploy.pub` to that user's `~/.ssh/authorized_keys`.
3. Get the server's host key: `ssh-keyscan -t ed25519 <server-ip>`.
4. In GitHub, Settings, Secrets and variables, Actions, add these secrets:

| Secret | Value |
| --- | --- |
| `VPS_HOST` | server IP or hostname |
| `VPS_USER` | the deploy user |
| `VPS_SSH_KEY` | contents of the private key `draftly-deploy` |
| `VPS_KNOWN_HOSTS` | the `ssh-keyscan` line from step 3 |
| `VPS_PORT` | optional; only if SSH is not on 22 |

If the clone is not in `~/draftly-platform`, set the repository variable
`VPS_REPO_DIR` to its path relative to the home directory. Delete the private
key from your machine once it is stored in GitHub.

The server needs read access to the private research repository for the
retrieval image (see above): the same credentials as the clone, or
`RESEARCH_REPO_URL` with a read-only token in `deploy/.env`.

### Retrieval engine

The retrieval API is not public. The backend reaches it at
`http://retrieval:8000`; you reach it through an SSH tunnel:

```bash
ssh -L 8001:127.0.0.1:8001 user@server
curl 'http://127.0.0.1:8001/search?q=prescription'
curl 'http://127.0.0.1:8001/similar-cases?q=deed+of+gift+revocation'
```

The image serves indexes built at image build time. It starts through
`retrieval/serve_frozen.py`, which uses the corpus fingerprints recorded
during the build instead of re-hashing a corpus the image does not contain.
That stands in for the research repo's `DRAFTLY_INDEX_FROZEN` mode, which is
not on its main branch yet.

### Day to day

```bash
deploy/vps.sh update           # git pull + research update + rebuild + restart
deploy/vps.sh deploy backend   # rebuild one image (backend or retrieval) and restart
deploy/vps.sh status           # containers, memory, health checks
deploy/vps.sh logs backend     # follow one service's logs
deploy/vps.sh down             # stop (data volumes are kept)
```

## Rules for a 1 GB VPS

- **Do not build on the VPS.** `next build` and the index build need more memory
  than the machine has. Build on a dev machine and ship the images.
- `build.sh` builds for `linux/amd64` by default, so a build on an Apple Silicon
  Mac produces images the VPS can run. Override with `PLATFORM=linux/arm64`.
- Give the VPS 2 GB of swap (commands below).
- Each service has a `mem_limit`. Measured idle use on a local run was about
  60 MB (frontend), 85 MB (backend), 70 MB (retrieval) and 15 MB (Caddy).

## Configure

```bash
cd deploy
cp .env.example .env   # git-ignored; fill in every value
```

`DOMAIN` must already point at the VPS (DNS A record) so Caddy can get a
certificate. The frontend image is built with
`NEXT_PUBLIC_API_BASE_URL=https://<DOMAIN>`, so changing the domain or the Clerk
publishable key means rebuilding the frontend image.

## Build (dev machine)

Everything needed to host Draftly is in this repository. The research repository
is only a build-time input for the retrieval image (its code and corpus), and is
expected next to this one at `../draftly`. Set `RETRIEVAL_CONTEXT` in `.env` if it
is elsewhere.

```bash
deploy/build.sh              # builds all three images for linux/amd64 and packs them
deploy/build.sh frontend     # or rebuild only what changed
```

The result is `deploy/dist/draftly-images.tar.gz` (git-ignored). The retrieval
image indexes the corpus during the build, which takes under a minute. Setting
`RETRIEVAL_WITH_EMBEDDINGS=1` also embeds every section and case with Gemini
during the build. That enables the dense search channel and spends Gemini
credits, so it is off by default. The key is passed as a build secret and is not
stored in the image.

## Prepare the server (once)

```bash
curl -fsSL https://get.docker.com | sudo sh      # not the snap package
sudo usermod -aG docker $USER                    # then log out and back in

# 2 GB of swap, if `free -h` shows none
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

Open ports 80 and 443 (TCP) and 443 (UDP) in the provider's firewall, and point
the `DOMAIN` DNS record at the server before the first start so Caddy can get a
certificate.

## Deploy

```bash
deploy/ship.sh user@server            # copy images and config, load, start
deploy/ship.sh user@server --config   # only .env, Caddyfile or compose changed
```

`ship.sh` copies `docker-compose.yml`, `Caddyfile`, `.env` and the packed images
to `~/draftly` on the server, loads the images and runs `docker compose up -d`.
Migrations run on every start. Check the result:

```bash
curl -s https://<DOMAIN>/health/ready
ssh user@server 'cd draftly && docker compose ps && docker stats --no-stream'
```

## Update and roll back

To update, rebuild what changed and ship again:

```bash
deploy/build.sh backend && deploy/ship.sh user@server
```

To be able to roll back, give each release its own tag in `.env` (for example
`draftly-backend:2026-09-20`) instead of reusing one tag. Rolling back is then
putting the previous tags in `.env` and running `deploy/ship.sh user@server
--config`, as long as the old images are still on the server. Alembic
migrations are not reversed automatically.

## Known limitations

- **`ENVIRONMENT=production` needs approved providers.** The backend refuses
  filesystem source-file storage, stub extraction and the stub matter-access
  adapter behind parties outside `local`, `test` and `ci`
  (`backend/src/bootstrap.py`, `modules/party/infrastructure/`). Production
  needs GCS storage with `DRAFTLY_STORAGE_REAL_DATA_APPROVED`, an approved
  extraction provider and the real matter-access adapter. Until then the API
  starts, but those features fail on first use. This is a backend decision, not
  a Docker one. The Vercel + VPS path runs `local` for that reason.
- **The backend does not call the retrieval service yet.** `modules/research` is
  empty. The stack passes `RETRIEVAL_BASE_URL=http://retrieval:8000` to the
  backend for when that client is written.
- **The retrieval service has no authentication.** It is deliberately not
  published and Caddy has no route to it. Do not add a `ports:` entry to it.
