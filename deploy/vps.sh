#!/usr/bin/env bash
# Run Draftly on one VPS, from a clone of this repository.
#
#   sudo deploy/vps.sh setup    # once: Docker, swap, firewall, fail2ban, auto-updates, backup cron
#   deploy/vps.sh init          # once: write deploy/.env with generated secrets
#   deploy/vps.sh deploy        # fetch retrieval inputs, build, start, check (rolls back on failure)
#   deploy/vps.sh update        # git pull, then deploy
#   deploy/vps.sh rollback      # put the previous images back
#   deploy/vps.sh backup        # archive the app's Docker volumes to /var/backups/draftly
#   deploy/vps.sh grant-trial --user usr_... --days N   # give an account a plan (unlocks research etc.)
#   deploy/vps.sh status        # containers, memory, health
#   deploy/vps.sh logs [svc]    # follow logs (all services, or one)
#   deploy/vps.sh down          # stop the stack (volumes are kept)
#
# Stack: docker-compose.vps.yml (Caddy, migrate, backend, worker, retrieval,
# optional bundled Postgres). Runs on synthetic data: see README.md,
# "Known limitations".
#
# WEB_ON_VPS=1 in deploy/.env also runs the frontend and the landing page here,
# so nothing is hosted on Vercel. See README.md, "Everything on one VPS".
set -euo pipefail

DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$DEPLOY_DIR")"
ENV_FILE="$DEPLOY_DIR/.env"
RESEARCH_DIR="$DEPLOY_DIR/.research"
SWAP_TARGET_MB=2048
BACKUP_DIR="${BACKUP_DIR:-/var/backups/draftly}"
BACKUP_KEEP=14
SNAPSHOT_FILE="$DEPLOY_DIR/.rollback"

say() { printf '\n==> %s\n' "$*"; }
warn() { printf 'warning: %s\n' "$*" >&2; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

# ── .env helpers (the file is read as data, never sourced) ────────────────────
env_value() { [ -f "$ENV_FILE" ] && sed -n "s/^$1=//p" "$ENV_FILE" | tail -n 1 || true; }

set_env() {
  local key="$1" value="$2" tmp
  tmp="$(mktemp)"
  if grep -q "^$key=" "$ENV_FILE"; then
    KEY="$key" VALUE="$value" awk 'BEGIN { k = ENVIRON["KEY"]; v = ENVIRON["VALUE"] }
      index($0, k "=") == 1 { print k "=" v; next } { print }' "$ENV_FILE" > "$tmp"
  else
    cat "$ENV_FILE" > "$tmp"
    printf '%s=%s\n' "$key" "$value" >> "$tmp"
  fi
  cat "$tmp" > "$ENV_FILE"
  rm -f "$tmp"
}

# Set only when the key is missing or empty, so init never clobbers a value.
default_env() { [ -n "$(env_value "$1")" ] || set_env "$1" "$2"; }

fernet_key() { openssl rand -base64 32 | tr '+/' '-_' | tr -d '\n'; }

# ── Docker compose with the VPS overlay and the right profiles ───────────────
web_on_vps() { [ "$(env_value WEB_ON_VPS)" = "1" ]; }

uses_local_db() { case "$(env_value DATABASE_URL)" in *@db:5432/*) return 0 ;; *) return 1 ;; esac; }

compose() {
  local profiles=()
  uses_local_db && profiles+=(--profile localdb)
  web_on_vps && profiles+=(--profile web)
  docker compose --project-name draftly --env-file "$ENV_FILE" \
    -f "$DEPLOY_DIR/docker-compose.vps.yml" ${profiles[@]+"${profiles[@]}"} "$@"
}

# ── setup ─────────────────────────────────────────────────────────────────────
cmd_setup() {
  [ "$(id -u)" -eq 0 ] || die "run setup with sudo: sudo deploy/vps.sh setup"
  local user="${SUDO_USER:-root}"

  say "installing base packages"
  if command -v apt-get >/dev/null; then
    apt-get update -qq
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq ca-certificates curl git openssl \
      fail2ban unattended-upgrades ufw git-lfs >/dev/null
    systemctl enable --now fail2ban >/dev/null 2>&1 || true
    printf 'APT::Periodic::Update-Package-Lists "1";\nAPT::Periodic::Unattended-Upgrade "1";\n' \
      > /etc/apt/apt.conf.d/20auto-upgrades
  else
    warn "not a Debian/Ubuntu system; make sure curl, git and openssl are installed"
  fi

  if ! command -v docker >/dev/null; then
    say "installing Docker (get.docker.com)"
    curl -fsSL https://get.docker.com | sh
  fi
  docker compose version >/dev/null 2>&1 || die "Docker is installed but the compose plugin is missing"
  systemctl enable --now docker >/dev/null 2>&1 || true
  if [ "$user" != "root" ] && ! id -nG "$user" | grep -qw docker; then
    usermod -aG docker "$user"
    echo "Added $user to the docker group. Log out and back in before running init/deploy."
  fi

  local swap_mb
  swap_mb="$(awk '/SwapTotal/ { print int($2 / 1024) }' /proc/meminfo)"
  if [ "$swap_mb" -lt $((SWAP_TARGET_MB - 256)) ]; then
    if [ -e /swapfile ]; then
      warn "/swapfile exists but total swap is only ${swap_mb} MB; leaving it alone"
    else
      say "creating ${SWAP_TARGET_MB} MB swap at /swapfile (headroom for image builds)"
      fallocate -l "${SWAP_TARGET_MB}M" /swapfile 2>/dev/null \
        || dd if=/dev/zero of=/swapfile bs=1M count="$SWAP_TARGET_MB" status=none
      chmod 600 /swapfile
      mkswap /swapfile >/dev/null
      swapon /swapfile
      grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
    fi
  fi
  # Prefer RAM for the running services; swap is mostly for build peaks.
  sysctl -q vm.swappiness=10
  echo 'vm.swappiness=10' > /etc/sysctl.d/99-draftly-swap.conf

  if command -v ufw >/dev/null; then
    say "firewall: deny incoming except 22, 80 and 443 (ufw)"
    ufw default deny incoming >/dev/null
    ufw default allow outgoing >/dev/null
    ufw allow 22/tcp >/dev/null
    ufw allow 80/tcp >/dev/null
    ufw allow 443/tcp >/dev/null
    ufw allow 443/udp >/dev/null
    ufw --force enable >/dev/null
  fi

  say "nightly volume backup (03:15) into $BACKUP_DIR"
  install -d -m 700 -o "$user" -g "$user" "$BACKUP_DIR"
  printf '15 3 * * * %s %s backup >> %s/backup.log 2>&1\n' "$user" "$DEPLOY_DIR/vps.sh" "$BACKUP_DIR" \
    > /etc/cron.d/draftly-backup
  chmod 644 /etc/cron.d/draftly-backup

  free -h
  echo
  echo "Setup done. If your provider has its own firewall, also open 80/tcp, 443/tcp and 443/udp."
  echo "Next: deploy/vps.sh init"
}

# ── init ──────────────────────────────────────────────────────────────────────
research_url_default() {
  local origin
  origin="$(git -C "$REPO_DIR" remote get-url origin 2>/dev/null || true)"
  case "$origin" in
    *draftly-platform*) printf '%s' "${origin/draftly-platform/draftly-research}" ;;
    *) printf '%s' "https://github.com/Draftly-LK/draftly-research.git" ;;
  esac
}

public_ip() {
  curl -fsS4 --max-time 5 https://api.ipify.org 2>/dev/null \
    || curl -fsS4 --max-time 5 https://ifconfig.me 2>/dev/null \
    || true
}

cmd_init() {
  command -v openssl >/dev/null || die "openssl is required (run: sudo deploy/vps.sh setup)"
  if [ ! -f "$ENV_FILE" ]; then
    cp "$DEPLOY_DIR/.env.example" "$ENV_FILE"
    chmod 600 "$ENV_FILE"
    say "created deploy/.env from .env.example"
  else
    say "deploy/.env exists; filling in only what is empty"
  fi

  if [ -z "$(env_value DOMAIN)" ] || [ "$(env_value DOMAIN)" = "app.example.com" ]; then
    local ip
    ip="$(public_ip)"
    if [ -n "$ip" ]; then
      # The API's address. sslip.io resolves a-b-c-d.sslip.io to a.b.c.d, so
      # Caddy can get a real certificate without buying a domain.
      set_env DOMAIN "${ip//./-}.sslip.io"
    else
      warn "could not detect the public IP; set DOMAIN in deploy/.env yourself"
    fi
  fi

  # Temporary demo on synthetic data: the local adapters (disk evidence store,
  # stub extraction, stub matter access for parties) only start in "local".
  # Real sign-in is still enforced: deploy refuses to run without Clerk keys.
  set_env ENVIRONMENT local
  # build.sh expects all three names; the frontend one is unused here (Vercel).
  set_env FRONTEND_IMAGE draftly-frontend:vps
  set_env BACKEND_IMAGE draftly-backend:vps
  set_env RETRIEVAL_IMAGE draftly-retrieval:vps
  set_env LANDING_IMAGE draftly-landing:vps
  # 1 = frontend and landing page run on this server too (no Vercel).
  default_env WEB_ON_VPS "${WEB_ON_VPS:-0}"
  default_env EXTRACTION_PROVIDER stub
  default_env PARTY_IDENTIFIER_KEY "$(fernet_key)"
  default_env PARTY_BLIND_INDEX_KEY "$(openssl rand -hex 32)"
  default_env API_CURSOR_SIGNING_KEY "$(openssl rand -hex 32)"
  default_env RESEARCH_REPO_URL "$(research_url_default)"
  default_env RESEARCH_REF main

  if [ -z "$(env_value DATABASE_URL)" ]; then
    local pw
    pw="$(openssl rand -hex 24)"
    set_env POSTGRES_PASSWORD "$pw"
    set_env DATABASE_URL "postgresql+psycopg://draftly:$pw@db:5432/draftly"
    set_env DATABASE_URL_DIRECT "postgresql+psycopg://draftly:$pw@db:5432/draftly"
    echo "No DATABASE_URL given: using the bundled Postgres container."
  fi

  if web_on_vps; then
    # sslip.io resolves any prefix, so the landing page gets its own hostname
    # (and certificate) without another domain. Use a real one if you have it.
    [ -n "$(env_value LANDING_DOMAIN)" ] || set_env LANDING_DOMAIN "landing.$(env_value DOMAIN)"
    default_env FRONTEND_ORIGIN "https://$(env_value DOMAIN)"
    echo
    echo "deploy/.env is ready except for the values only you have. Edit it and set:"
    echo "  NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY  (pk_... from your Clerk instance)"
    echo "  CLERK_SECRET_KEY                   (sk_... from the same instance)"
    echo "  GEMINI_API_KEY                     (optional: retrieval /answer and Gemini extraction)"
    echo "Add https://$(env_value DOMAIN) to the allowed origins in the Clerk dashboard."
    echo "App:          https://$(env_value DOMAIN)"
    echo "Landing page: https://$(env_value LANDING_DOMAIN)"
    echo "Next: deploy/vps.sh deploy"
    return
  fi

  echo
  default_env FRONTEND_ORIGIN ""
  echo "deploy/.env is ready except for the values only you have. Edit it and set:"
  echo "  FRONTEND_ORIGIN                    (your Vercel URL, e.g. https://draftly-demo.vercel.app)"
  echo "  NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY  (pk_test_... from a Clerk development instance)"
  echo "  CLERK_SECRET_KEY                   (sk_test_... from the same instance)"
  echo "  GEMINI_API_KEY                     (optional: retrieval /answer and Gemini extraction)"
  echo "CLERK_ISSUER is worked out from the publishable key, CLERK_AUTHORIZED_PARTY from FRONTEND_ORIGIN."
  echo "API address (Vercel's NEXT_PUBLIC_API_BASE_URL): https://$(env_value DOMAIN)"
  echo "Next: deploy/vps.sh deploy"
}

# ── deploy ────────────────────────────────────────────────────────────────────
# pk_test_<base64 of "<frontend-api-host>$"> -> https://<frontend-api-host>
clerk_issuer_from_key() {
  local encoded="${1#pk_test_}"
  encoded="${encoded#pk_live_}"
  while [ $(( ${#encoded} % 4 )) -ne 0 ]; do encoded="$encoded="; done
  local host
  host="$(printf '%s' "$encoded" | base64 -d 2>/dev/null | tr -d '$\n' || true)"
  [ -z "$host" ] || printf 'https://%s' "$host"
}

check_config() {
  [ -f "$ENV_FILE" ] || die "missing deploy/.env (run: deploy/vps.sh init)"
  docker info >/dev/null 2>&1 || die "cannot reach Docker (run setup, then log out and back in)"

  local pk issuer
  pk="$(env_value NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)"
  if [ -n "$pk" ] && [ -z "$(env_value CLERK_ISSUER)" ]; then
    issuer="$(clerk_issuer_from_key "$pk")"
    [ -n "$issuer" ] && set_env CLERK_ISSUER "$issuer"
  fi
  local origin
  if web_on_vps; then
    # One origin: the app and the API share DOMAIN, so nothing is cross-origin.
    set_env CADDYFILE ./Caddyfile.full
    set_env FRONTEND_ORIGIN "https://$(env_value DOMAIN)"
    [ -n "$(env_value LANDING_DOMAIN)" ] || set_env LANDING_DOMAIN "landing.$(env_value DOMAIN)"
  else
    set_env CADDYFILE ./Caddyfile.api
  fi
  origin="$(env_value FRONTEND_ORIGIN)"
  case "$origin" in
    "") ;;
    https://*) origin="${origin%/}"; set_env FRONTEND_ORIGIN "$origin" ;;
    *) die "FRONTEND_ORIGIN must be an https:// origin such as https://draftly-demo.vercel.app" ;;
  esac
  [ -z "$origin" ] || [ -n "$(env_value CLERK_AUTHORIZED_PARTY)" ] || set_env CLERK_AUTHORIZED_PARTY "$origin"

  local key missing=()
  for key in DOMAIN FRONTEND_ORIGIN DATABASE_URL DATABASE_URL_DIRECT \
             CLERK_SECRET_KEY CLERK_ISSUER CLERK_AUTHORIZED_PARTY \
             PARTY_IDENTIFIER_KEY PARTY_BLIND_INDEX_KEY API_CURSOR_SIGNING_KEY; do
    [ -n "$(env_value "$key")" ] || missing+=("$key")
  done
  uses_local_db && { [ -n "$(env_value POSTGRES_PASSWORD)" ] || missing+=(POSTGRES_PASSWORD); }
  if web_on_vps; then
    # Inlined into the frontend bundle at build time.
    for key in LANDING_DOMAIN NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY; do
      [ -n "$(env_value "$key")" ] || missing+=("$key")
    done
  fi
  # Without Clerk, "local" would fall back to the stub identity, which accepts
  # any bearer token. That must never be reachable from the internet.
  [ ${#missing[@]} -eq 0 ] || die "set these in deploy/.env first: ${missing[*]}"
  case "$(env_value USE_STUB_IDENTITY)" in true|1) die "USE_STUB_IDENTITY must not be on for a public server" ;; esac

  if [ -r /proc/meminfo ]; then
    local total_mb
    total_mb="$(awk '/MemTotal|SwapTotal/ { t += $2 } END { print int(t / 1024) }' /proc/meminfo)"
    [ "$total_mb" -ge 2500 ] || warn "RAM + swap is ${total_mb} MB; image builds may be killed. Run: sudo deploy/vps.sh setup"
  fi
  local free_gb
  free_gb="$(df -Pk "$DEPLOY_DIR" | awk 'NR == 2 { print int($4 / 1048576) }')"
  [ "$free_gb" -ge 5 ] || warn "only ${free_gb} GB free disk; the build needs about 5 GB"
}

# Only the paths the retrieval image copies, taken from its dockerignore
# allowlist, so the clone skips the rest of the (large, private) research repo.
research_paths() {
  sed -n 's/^!\(.*\)$/\/\1/p' "$DEPLOY_DIR/retrieval/Dockerfile.dockerignore"
}

fetch_research() {
  command -v git-lfs >/dev/null \
    || die "git-lfs is required: the research corpus keeps its judgment files in Git LFS (run: sudo deploy/vps.sh setup)"
  local url ref
  url="$(env_value RESEARCH_REPO_URL)"
  url="${url:-$(research_url_default)}"
  ref="$(env_value RESEARCH_REF)"
  ref="${ref:-main}"

  if [ ! -d "$RESEARCH_DIR/.git" ]; then
    say "fetching retrieval inputs from the research repo ($ref, sparse)"
    rm -rf "$RESEARCH_DIR"
    git clone --quiet --filter=blob:none --no-checkout --depth 1 --branch "$ref" "$url" "$RESEARCH_DIR" \
      || die "could not clone $url. It is private: clone this repo with credentials that can also read it, or set RESEARCH_REPO_URL in deploy/.env (e.g. https://<token>@github.com/Draftly-LK/draftly-research.git)."
    # shellcheck disable=SC2046  # one pattern per line, none contain spaces
    git -C "$RESEARCH_DIR" sparse-checkout set --no-cone $(research_paths)
    git -C "$RESEARCH_DIR" checkout --quiet "$ref"
  else
    say "updating retrieval inputs from the research repo ($ref)"
    git -C "$RESEARCH_DIR" sparse-checkout set --no-cone $(research_paths)
    git -C "$RESEARCH_DIR" fetch --quiet --filter=blob:none --depth 1 origin "$ref"
    git -C "$RESEARCH_DIR" reset --quiet --hard FETCH_HEAD
  fi
  # A checkout made before git-lfs was installed leaves LFS pointer files. Delete
  # each one and let git check it out again: the LFS smudge filter then downloads
  # just that object. (`git lfs pull` is not used: on this partial clone it scans
  # the whole tree and fetches blobs one by one, which takes tens of minutes.)
  git -C "$RESEARCH_DIR" lfs install --local >/dev/null
  local pointer rel
  while IFS= read -r pointer; do
    rel="${pointer#"$RESEARCH_DIR"/}"
    say "downloading LFS file $rel"
    rm -f "$pointer"
    git -C "$RESEARCH_DIR" checkout -- "$rel" \
      || die "could not download $rel from Git LFS (does the deploy key have read access to LFS objects?)"
  done < <(grep -rlm1 --exclude-dir=.git '^version https://git-lfs.github.com/spec/v1' "$RESEARCH_DIR" 2>/dev/null || true)
  pointer="$(grep -rlm1 --exclude-dir=.git '^version https://git-lfs.github.com/spec/v1' "$RESEARCH_DIR" 2>/dev/null | head -n 1 || true)"
  [ -z "$pointer" ] || die "$pointer is still a Git LFS pointer; the retrieval index cannot be built from it"
  echo "research repo at $(git -C "$RESEARCH_DIR" rev-parse --short HEAD)"
}

native_platform() {
  case "$(uname -m)" in
    x86_64 | amd64) echo linux/amd64 ;;
    aarch64 | arm64) echo linux/arm64 ;;
    *) die "unsupported CPU architecture $(uname -m)" ;;
  esac
}

build_images() {
  local targets=("$@") target
  if [ ${#targets[@]} -eq 0 ]; then
    targets=(backend retrieval)
    web_on_vps && targets+=(frontend landing)
  fi
  for target in "${targets[@]}"; do
    case "$target" in
      backend | retrieval) ;;
      frontend | landing)
        web_on_vps || die "'$target' is only built here when WEB_ON_VPS=1 (otherwise Vercel builds the frontend)" ;;
      *) die "unknown image '$target' (use: backend retrieval frontend landing)" ;;
    esac
  done
  say "building ${targets[*]}"
  # `|| return 1`: cmd_deploy calls this in an `||` list, where set -e is off.
  PACK=0 PLATFORM="$(native_platform)" RETRIEVAL_CONTEXT="$RESEARCH_DIR" \
    "$DEPLOY_DIR/build.sh" "${targets[@]}" || return 1
  # The :previous tags (see snapshot_images) keep the last release's layers alive.
  docker image prune -f >/dev/null
  docker builder prune -f --filter until=168h >/dev/null 2>&1 || true
}

# ── rollback ──────────────────────────────────────────────────────────────────
# Before a build, remember which image each tag points at and pin it as
# <name>:previous. A failed deploy puts those images back automatically; the
# `rollback` command does the same for a release that turned out to be bad.
# Database migrations are forward-only and are NOT reverted (see README.md).
image_names() {
  local var name
  for var in BACKEND_IMAGE RETRIEVAL_IMAGE FRONTEND_IMAGE LANDING_IMAGE; do
    name="$(env_value "$var")"
    [ -n "$name" ] && echo "$name"
  done
  return 0
}

snapshot_images() {
  local name id tmp
  tmp="$(mktemp)"
  while IFS= read -r name; do
    id="$(docker image inspect --format '{{.Id}}' "$name" 2>/dev/null || true)"
    [ -n "$id" ] || continue
    docker tag "$id" "${name%%:*}:previous"
    printf '%s=%s\n' "$name" "$id" >> "$tmp"
  done < <(image_names)
  mv "$tmp" "$SNAPSHOT_FILE"
}

restart_stack() {
  compose up -d --remove-orphans --no-build --wait --wait-timeout 300
}

# Re-point every tag at the image recorded before this deploy started.
restore_snapshot() {
  local name id restored=0
  [ -s "$SNAPSHOT_FILE" ] || { warn "no previous release recorded (first deploy?); nothing to roll back to"; return 1; }
  while IFS='=' read -r name id; do
    [ -n "$name" ] && [ -n "$id" ] || continue
    docker tag "$id" "$name" && restored=1
  done < "$SNAPSHOT_FILE"
  [ "$restored" -eq 1 ]
}

rollback_after_failure() {
  warn "deploy failed: restoring the previous release"
  if restore_snapshot && restart_stack; then
    warn "rolled back; the previous release is running again"
  else
    warn "automatic rollback did not succeed; inspect with: deploy/vps.sh status"
  fi
}

cmd_rollback() {
  [ -f "$ENV_FILE" ] || die "missing deploy/.env"
  local name prev found=0
  while IFS= read -r name; do
    prev="${name%%:*}:previous"
    docker image inspect "$prev" >/dev/null 2>&1 || continue
    docker tag "$prev" "$name"
    found=1
  done < <(image_names)
  [ "$found" -eq 1 ] || die "no :previous images on this server; nothing to roll back to"
  say "restarting on the previous images"
  restart_stack || die "the previous release did not become healthy; see: deploy/vps.sh logs"
  verify || exit 1
}

# ── backup ────────────────────────────────────────────────────────────────────
# Archives what lives on the server: pilot-request emails, uploaded source files
# and, when DATABASE_URL points at the bundled Postgres, the database itself.
# ── grant-trial ───────────────────────────────────────────────────────────────
# Gated features (research, drafting, export, document processing) are denied to
# an account with no subscription. This runs the billing service's own
# grant_trial inside the backend container: see backend/src/cli/grant_trial.py.
# The acting admin must be listed in PLATFORM_ADMIN_USER_IDS in deploy/.env.
cmd_grant_trial() {
  [ $# -gt 0 ] || die "usage: deploy/vps.sh grant-trial --user usr_... --days N [--plan plan_trial_v1] [--admin usr_...]"
  compose exec -T backend python -m src.cli.grant_trial "$@"
}

cmd_backup() {
  local stamp vol
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  install -d -m 700 "$BACKUP_DIR" 2>/dev/null || die "cannot write $BACKUP_DIR (run: sudo deploy/vps.sh setup)"
  for vol in draftly_pilot-requests draftly_source-files; do
    docker volume inspect "$vol" >/dev/null 2>&1 || continue
    # As the calling user, umask 077: the archives hold email addresses.
    docker run --rm --user "$(id -u):$(id -g)" -v "$vol:/data:ro" -v "$BACKUP_DIR:/out" alpine \
      sh -c 'umask 077 && tar -czf "/out/$1" -C /data .' _ "${vol#draftly_}-$stamp.tar.gz"
    echo "backed up $vol -> $BACKUP_DIR/${vol#draftly_}-$stamp.tar.gz"
  done
  # The local PostgreSQL (when DATABASE_URL points at it): a custom-format dump,
  # restorable with pg_restore. Mode 600, like the volume archives.
  if uses_local_db && compose ps --status running --services 2>/dev/null | grep -qx db; then
    ( umask 077; compose exec -T db pg_dump -U draftly -Fc draftly > "$BACKUP_DIR/database-$stamp.dump" ) \
      || die "pg_dump failed"
    echo "backed up database -> $BACKUP_DIR/database-$stamp.dump"
  fi
  # Keep the newest $BACKUP_KEEP archives of each volume.
  for vol in pilot-requests source-files; do
    # shellcheck disable=SC2012  # names are ours: <vol>-<timestamp>.tar.gz
    ls -1t "$BACKUP_DIR/$vol"-*.tar.gz 2>/dev/null | tail -n +$((BACKUP_KEEP + 1)) | xargs -r rm -f
  done
  # shellcheck disable=SC2012
  ls -1t "$BACKUP_DIR"/database-*.dump 2>/dev/null | tail -n +$((BACKUP_KEEP + 1)) | xargs -r rm -f
}

verify() {
  local domain
  domain="$(env_value DOMAIN)"
  say "checking the running stack"
  compose ps --format 'table {{.Service}}\t{{.State}}\t{{.Status}}'

  local ok=1 ready retrieval origin cors
  ready="$(curl -fsSk --max-time 20 --resolve "$domain:443:127.0.0.1" "https://$domain/health/ready" || true)"
  if [ -n "$ready" ]; then echo "backend   /health/ready: $ready"; else echo "backend   /health/ready: FAILED"; ok=0; fi
  retrieval="$(curl -fsS --max-time 20 http://127.0.0.1:8001/health || true)"
  if [ -n "$retrieval" ]; then echo "retrieval /health: $(printf '%s' "$retrieval" | cut -c1-120)..."; else echo "retrieval /health: FAILED"; ok=0; fi
  origin="$(env_value FRONTEND_ORIGIN)"
  if web_on_vps; then
    # Same origin, so there is no CORS to check; check each site instead.
    local landing code
    landing="$(env_value LANDING_DOMAIN)"
    code="$(curl -sk -o /dev/null -w '%{http_code}' --max-time 30 --resolve "$domain:443:127.0.0.1" "https://$domain/" || true)"
    case "$code" in 2* | 3*) echo "frontend  https://$domain/: HTTP $code" ;; *) echo "frontend  https://$domain/: FAILED (HTTP ${code:-none})"; ok=0 ;; esac
    code="$(curl -sk -o /dev/null -w '%{http_code}' --max-time 30 --resolve "$landing:443:127.0.0.1" "https://$landing/" || true)"
    case "$code" in 2*) echo "landing   https://$landing/: HTTP $code" ;; *) echo "landing   https://$landing/: FAILED (HTTP ${code:-none})"; ok=0 ;; esac
  else
  cors="$(curl -sk -o /dev/null -D - --max-time 20 --resolve "$domain:443:127.0.0.1" -X OPTIONS \
    -H "Origin: $origin" -H "Access-Control-Request-Method: GET" -H "Access-Control-Request-Headers: authorization" \
    "https://$domain/api/v1/me" | tr -d '\r' | awk 'tolower($0) ~ /^access-control-allow-origin:/ { sub(/^[^:]*: */, ""); print }' || true)"
  if [ "$cors" = "$origin" ]; then echo "CORS      $origin: allowed"; else echo "CORS      $origin: NOT allowed"; ok=0; fi
  fi

  if curl -fsS -o /dev/null --max-time 20 "https://$domain/health/live" 2>/dev/null; then
    echo "certificate: valid for $domain"
  else
    warn "https://$domain is not reachable from here with a valid certificate yet. Check DNS, ports 80/443 in the provider firewall, and: deploy/vps.sh logs caddy"
  fi

  if [ "$ok" -ne 1 ]; then
    warn "some checks failed; see: deploy/vps.sh logs"
    return 1
  fi
  echo
  if web_on_vps; then
    echo "App is up:    https://$domain"
    echo "Landing page: https://$(env_value LANDING_DOMAIN)"
  else
    echo "API is up: https://$domain"
    echo "In Vercel set NEXT_PUBLIC_API_BASE_URL=https://$domain and open $origin"
  fi
  echo "Retrieval (not public): ssh -L 8001:127.0.0.1:8001 <you>@<server>, then http://127.0.0.1:8001/health"
}

cmd_deploy() {
  check_config
  fetch_research
  snapshot_images
  # The running containers keep their old images until `up`, so a failed build
  # leaves the site untouched; just put the tags back for the next attempt.
  build_images "$@" || { restore_snapshot || true; die "image build failed; the running stack was not touched"; }
  say "starting the stack (migrations run first)"
  if ! compose up -d --remove-orphans --wait --wait-timeout 300; then
    compose ps -a
    rollback_after_failure
    die "the stack did not become healthy; see: deploy/vps.sh logs"
  fi
  if ! verify; then
    rollback_after_failure
    exit 1
  fi
}

cmd_update() {
  say "pulling this repository"
  git -C "$REPO_DIR" pull --ff-only
  cmd_deploy "$@"
}

cmd_status() {
  compose ps -a
  echo
  docker stats --no-stream --format 'table {{.Name}}\t{{.MemUsage}}\t{{.CPUPerc}}'
  echo
  free -h 2>/dev/null || true
  verify || true
}

case "${1:-}" in
  setup) cmd_setup ;;
  init) cmd_init ;;
  deploy) shift; cmd_deploy "$@" ;;
  update) shift; cmd_update "$@" ;;
  rollback) cmd_rollback ;;
  backup) cmd_backup ;;
  grant-trial) shift; cmd_grant_trial "$@" ;;
  status) cmd_status ;;
  logs) shift; compose logs -f --tail 200 "$@" ;;
  down) compose down ;;
  *) sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'; exit 1 ;;
esac
