#!/usr/bin/env bash
# Forced command for the GitHub Actions deploy key (see deploy/README.md,
# "Continuous delivery"). Installed root-owned, outside the repository, so the
# key can only ever run this file:
#
#   sudo install -m 755 deploy/ci-deploy.sh /usr/local/bin/draftly-ci-deploy
#
# and pinned in the deploy user's ~/.ssh/authorized_keys as
#
#   restrict,command="/usr/local/bin/draftly-ci-deploy" ssh-ed25519 AAAA... github-actions
#
# The workflow sends one of:
#   deploy <40-hex commit sha>   deploy that commit of the prod branch
#   rollback                     put the previous release back
set -euo pipefail

REPO_DIR="${DRAFTLY_REPO_DIR:-$HOME/draftly-platform}"
BRANCH="prod"

die() { echo "ci-deploy: $*" >&2; exit 1; }

read -r action sha extra <<<"${SSH_ORIGINAL_COMMAND:-}"
[ -z "${extra:-}" ] || die "unexpected arguments"

# One deploy at a time on the server, whatever GitHub's concurrency does.
exec 9>"$HOME/.draftly-deploy.lock"
flock -w 3600 9 || die "another deploy has held the lock for an hour"

cd "$REPO_DIR" || die "no clone at $REPO_DIR"

case "$action" in
  deploy)
    [[ "${sha:-}" =~ ^[0-9a-f]{40}$ ]] || die "usage: deploy <40-hex sha>"
    git fetch --quiet origin "$BRANCH"
    tip="$(git rev-parse "origin/$BRANCH")"
    if [ "$sha" != "$tip" ]; then
      # A newer commit reached prod while this run waited; its own run ships it.
      git merge-base --is-ancestor "$sha" "$tip" || die "$sha is not on origin/$BRANCH"
      echo "ci-deploy: $sha is superseded by $tip; skipping (the newer run deploys it)"
      exit 0
    fi
    git checkout --quiet -B "$BRANCH" "$tip"
    echo "ci-deploy: deploying $(git log -1 --format='%h %s')"
    # Run the freshly checked-out script, so a change to vps.sh ships itself.
    exec deploy/vps.sh deploy
    ;;
  rollback)
    exec deploy/vps.sh rollback
    ;;
  *)
    die "unknown command (use: deploy <sha> | rollback)"
    ;;
esac
