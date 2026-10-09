#!/usr/bin/env bash
# Bind a promotion's deployment request to the commit Actions actually selected.
# An ordinary manual redeploy need not supply EXPECTED_SHA.
set -euo pipefail

expected="${EXPECTED_SHA:-}"
[ -n "$expected" ] || exit 0
[[ "$expected" =~ ^[0-9a-f]{40}$ ]] || {
  echo "deploy: EXPECTED_SHA must be a 40-hex commit SHA" >&2
  exit 1
}
[ "$expected" = "${GITHUB_SHA:-}" ] || {
  echo "deploy: prod changed before dispatch; run promotion again" >&2
  exit 1
}
