# Case law review issues

## Primary button contrast

Found: the shared secondary-button style supplied `bg-surface`, while the primary
search button also requested `bg-forest` and white text. CSS ordering left white
text on white at rest; the first synthetic capture exposed it.

Fix: merge primary overrides through the existing class-merging helper, removing
conflicting background and hover classes.

Result: re-reviewed at both viewports and in Sinhala zoom; visible label and no
serious or critical axe contrast finding. Covering interaction tests pass.

## Existing development-route collision

Found: main contained both `/dev/gazette-page/[name]` and
`/dev/gazette-page/[lang]/[name]`. Next development startup rejected the conflicting
first-segment slug names before the case screen could be reviewed.

Fix: the one-segment handler now shares `[lang]` internally and aliases it to the
image name. Both URL shapes, filename validation and production 404 stay intact.
No gazette text or image asset changed.

Result: four focused route regression checks pass. Actual Next development
startup and the case-screen routes pass after the final build.

## Test harness corrections

The standalone bundle needed test-only framework adapters for Next navigation
and Clerk wrappers; production source gained no auth override. Native selects
and controlled textarea labels required role-based Playwright selectors. These
were harness corrections, not product changes.

Intentional 503/403 probes emit browser HTTP diagnostics. They are recorded
separately from application errors; positive-state captures have no unexpected
errors, warnings or failed assets.
