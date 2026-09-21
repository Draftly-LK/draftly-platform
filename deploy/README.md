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

Postgres is not in the stack. Use the managed Neon database: the pooled URL in
`DATABASE_URL` and the direct URL in `DATABASE_URL_DIRECT`.

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

- **Document upload with `ENVIRONMENT=production`.** The backend refuses
  filesystem source-file storage outside `local`, `test` and `ci`
  (`backend/src/bootstrap.py`), and no object-storage adapter exists yet. With
  `ENVIRONMENT=production` the API starts and serves, but document ingestion
  raises on first use. This is a backend decision, not a Docker one.
- **The backend does not call the retrieval service yet.** `modules/research` is
  empty. The stack passes `RETRIEVAL_BASE_URL=http://retrieval:8000` to the
  backend for when that client is written.
- **The retrieval service has no authentication.** It is deliberately not
  published and Caddy has no route to it. Do not add a `ports:` entry to it.
