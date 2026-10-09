# Direct fact acceptance review

Synthetic fixtures only. No live client facts were changed.

## Changes

- Pending fact rows offer **Accept** directly. Unchanged evidence-backed values
  need no association form or reason. Corrections use **Review or correct**.
- Server acceptance retains unassigned scope, original values, evidence pins,
  append-only decisions, authority checks, optimistic versions and replay keys.
- Unassigned observations from different documents are independent. They remain
  gaps for scoped work and cannot supply checks or approved form bindings.
- Assigned facts still require explicit conflict resolution. Missing or stale
  evidence opens detailed review. Refusals never optimistically confirm a value.
- Changed UI copy is English, as requested.

## Verification

- Frontend: 45 fact-screen/API regression tests passed. Tests cover direct
  acceptance and reload, refused writes, ambiguous retries with the same key and
  version, corrections, source access, scope changes and alternative review.
- Frontend lint and production build passed. Backend lock, Ruff checks and
  formatting, and mypy passed. Markdown lint passed across 153 files.
- Backend: 211 focused verification and migrated PostgreSQL regression tests
  passed. Synthetic machine observations and manual facts persist confirmation,
  evidence and history without invented associations. Unassigned values remain
  excluded from binding and cannot produce false scope conflicts.
- Playwright drove actual Chrome against the local frontend with a stateful
  synthetic API fixture: Accept, reload, review, correction with reason and
  history. See [browser results](browser-results.json) and the reproducible
  [browser harness](browser-smoke.cjs). The harness requires a local test token
  adapter; the production token provider was restored before build/commit.
- Two scoped axe audits found no serious or critical violations. Browser page
  errors were empty. Layout checks passed at 390, 1024 and 1440 pixels.
- Official Chrome DevTools CLI independently inspected a synthetic local page,
  clicked Accept, and inspected the result after reload. Result:
  `confirmed=true`, `reviewFields=0`, `acceptButtons=0`, `scopeUnassigned=true`.
  Its click command reported an interaction timeout after the request completed;
  subsequent DOM inspection and reload confirmed the saved state.
- Independent code review found a false downstream conflict for unrelated
  unassigned observations. A failing projection regression reproduced it; the
  fix retains unassigned gaps while excluding them from conflict calculation.
  Follow-up review found no remaining critical or important issues.

## Visual review

The shared primary button has a check icon and text; confirmed status has an icon
and text. The secondary review control remains alongside it. No visual blockers
were found in the synthetic screenshots.

- [Before acceptance](before-accept.png)
- [After correction, desktop](accepted-desktop.png)
- [1024 pixels](accepted-1024.png)
- [Mobile](accepted-mobile.png)

## Limits

Browser API responses were synthetic. Real persistence and evidence validation
were checked by separate PostgreSQL tests. Live authenticated inspection was
read-only; production rollout awaits merge and deployment.
