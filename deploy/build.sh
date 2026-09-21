#!/usr/bin/env bash
# Build the three Draftly images for the server and pack them into one file.
#
#   deploy/build.sh                 # build everything
#   deploy/build.sh frontend        # rebuild one or more: frontend backend retrieval
#
# Reads deploy/.env. Output: deploy/dist/draftly-images.tar.gz (git-ignored),
# which ship.sh copies to the server.
#
# vps.sh also calls this on the server itself with PACK=0 (keep the images in
# the local Docker, no tarball), PLATFORM set to the server's own platform and
# RETRIEVAL_CONTEXT pointing at its sparse research checkout.
set -euo pipefail

DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$DEPLOY_DIR")"
ENV_FILE="$DEPLOY_DIR/.env"
[ -f "$ENV_FILE" ] || { echo "Missing $ENV_FILE (copy .env.example and fill it in)." >&2; exit 1; }

# Read one KEY=value from .env without executing the file.
env_value() { sed -n "s/^$1=//p" "$ENV_FILE" | tail -n 1; }
require() { local v; v="$(env_value "$1")"; [ -n "$v" ] || { echo "$1 is empty in deploy/.env" >&2; exit 1; }; printf '%s' "$v"; }

PLATFORM="${PLATFORM:-linux/amd64}"
FRONTEND_IMAGE="$(require FRONTEND_IMAGE)"
BACKEND_IMAGE="$(require BACKEND_IMAGE)"
RETRIEVAL_IMAGE="$(require RETRIEVAL_IMAGE)"
RETRIEVAL_CONTEXT="${RETRIEVAL_CONTEXT:-$(env_value RETRIEVAL_CONTEXT)}"
RETRIEVAL_CONTEXT="${RETRIEVAL_CONTEXT:-$REPO_DIR/../draftly}"
PACK="${PACK:-1}"

targets=("$@")
[ ${#targets[@]} -gt 0 ] || targets=(backend retrieval frontend)

for target in "${targets[@]}"; do
  echo "==> building $target for $PLATFORM"
  case "$target" in
    backend)
      docker buildx build --platform "$PLATFORM" --load -t "$BACKEND_IMAGE" "$REPO_DIR/backend"
      ;;
    frontend)
      docker buildx build --platform "$PLATFORM" --load -t "$FRONTEND_IMAGE" \
        --build-arg "NEXT_PUBLIC_API_BASE_URL=https://$(require DOMAIN)" \
        --build-arg "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=$(require NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)" \
        --build-arg "NEXT_PUBLIC_USE_MOCK_PIPELINE=$(env_value NEXT_PUBLIC_USE_MOCK_PIPELINE)" \
        "$REPO_DIR/frontend"
      ;;
    retrieval)
      [ -d "$RETRIEVAL_CONTEXT/src/draftly/retrieval" ] || {
        echo "Research repo not found at $RETRIEVAL_CONTEXT (set RETRIEVAL_CONTEXT in deploy/.env)." >&2; exit 1; }
      embed_args=()
      if [ "$(env_value RETRIEVAL_WITH_EMBEDDINGS)" = "1" ]; then
        GEMINI_API_KEY="$(require GEMINI_API_KEY)"; export GEMINI_API_KEY
        embed_args=(--build-arg WITH_EMBEDDINGS=1 --secret id=gemini_api_key,env=GEMINI_API_KEY)
      fi
      docker buildx build --platform "$PLATFORM" --load -t "$RETRIEVAL_IMAGE" \
        -f "$DEPLOY_DIR/retrieval/Dockerfile" \
        --build-context "deploy=$DEPLOY_DIR/retrieval" \
        ${embed_args[@]+"${embed_args[@]}"} \
        "$RETRIEVAL_CONTEXT"
      ;;
    *) echo "Unknown target '$target' (use: frontend backend retrieval)" >&2; exit 1 ;;
  esac
done

[ "$PACK" = "1" ] || exit 0

for image in "$FRONTEND_IMAGE" "$BACKEND_IMAGE" "$RETRIEVAL_IMAGE"; do
  docker image inspect "$image" >/dev/null 2>&1 || {
    echo "Not packing yet: $image has not been built. Run deploy/build.sh with no arguments." >&2; exit 0; }
done

mkdir -p "$DEPLOY_DIR/dist"
echo "==> packing images"
docker save "$FRONTEND_IMAGE" "$BACKEND_IMAGE" "$RETRIEVAL_IMAGE" | gzip > "$DEPLOY_DIR/dist/draftly-images.tar.gz"
ls -lh "$DEPLOY_DIR/dist/draftly-images.tar.gz"
echo "Next: deploy/ship.sh user@server"
