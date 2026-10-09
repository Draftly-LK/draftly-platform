#!/usr/bin/env bash
# Fast-forward origin/prod to the exact main commit checked by the caller's CI.
# Deployment is dispatched separately by promote-prod.yml: a GITHUB_TOKEN push
# deliberately does not trigger another push workflow.
set -euo pipefail

die() { echo "promote-prod: $*" >&2; exit 1; }

sha="${PROMOTION_SHA:-}"
[[ "$sha" =~ ^[0-9a-f]{40}$ ]] || die "PROMOTION_SHA must be a 40-hex commit SHA"

git fetch --no-tags origin \
  +refs/heads/main:refs/remotes/origin/main \
  +refs/heads/prod:refs/remotes/origin/prod

main_tip="$(git rev-parse refs/remotes/origin/main)"
prod_tip="$(git rev-parse refs/remotes/origin/prod)"
[ "$sha" = "$main_tip" ] || die "main changed during CI; run promotion again"
git merge-base --is-ancestor "$prod_tip" "$sha" || \
  die "prod is not an ancestor of main; reconcile the branches by pull request"

# Fetch may take time. Recheck live main just before changing prod.
live_main="$(git ls-remote --exit-code origin refs/heads/main | awk '{print $1}')"
[ "$sha" = "$live_main" ] || die "main changed after fetch; run promotion again"

if [ "$prod_tip" = "$sha" ]; then
  echo "promote-prod: prod already matches $sha; deployment can be retried"
else
  # Never force-push. A concurrent incompatible prod update rejects this push.
  git push origin "$sha:refs/heads/prod"
  echo "promote-prod: prod advanced from $prod_tip to $sha"
fi
