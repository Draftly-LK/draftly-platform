# Verified facts review issues

## Iteration 1

- Found: conflict-candidate source snippets used `muted-ink` on `amber-bg`,
  producing 4.39:1 contrast at 12 px.
- Fix: used `ink` for the snippets while retaining `amber-text` for warning
  labels.
- Result: both viewports pass axe with the full comparison visible.

